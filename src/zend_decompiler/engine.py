#!/usr/bin/env python3
"""Current typed, fail-closed facade. Input files are READ, NEVER executed.

The single restoration core is shared by all entrypoints.
Results are experimental and do not assert behavioral equivalence.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from collections import Counter
import hashlib
import json
import re

from .restore_core import restore as restore_candidate
from .serial_parser import decompress_encoded, parse_binary, FormatError
from .calibrate import choose_opcode

__version__ = '29.0.0'
Status = Literal['candidate_generated', 'unsupported', 'not_encoded']

@dataclass(frozen=True)
class RestoreResult:
    code: bytes | None
    audit: dict
    status: Status
    reason: str | None = None


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(source: Path, dictionary: Path, mapping: Path, *, window: int = 2, isolate_parser: bool = False) -> dict:
    """Best-effort structural diagnostic; records only known mappings.

    Recognition is NOT proof of support by generator or semantic correctness.
    """
    streams=decompress_encoded(source,dictionary.read_bytes())
    if len(streams)!=1:
        raise FormatError(f'Expected one stream, observed {len(streams)}')
    if isolate_parser:
        from .parser_isolated import parse_isolated
        preflight=parse_isolated(streams[0][1])
        if preflight['status']!='parsed':
            raise FormatError('Isolated parser preflight rejected input: '+preflight.get('reason','unknown'))
    parsed=parse_binary(streams[0][1])
    mp=json.loads(mapping.read_text(encoding='utf8'))
    names=mp.get('names',{})
    metadata_path=mapping.with_name(mapping.name+'.meta.json')
    metadata=None
    if metadata_path.exists():
        metadata=json.loads(metadata_path.read_text(encoding='utf-8'))
        if metadata.get('mapping_sha256')!=_hash(mapping):
            raise FormatError('Opcode metadata SHA256 does not match supplied mapping')
        if metadata.get('mapping_file')!=mapping.name:
            raise FormatError('Opcode metadata mapping file mismatch')
    evidence_path=mapping.with_name(metadata['evidence_file'] if metadata else 'opcode_evidence.json')
    evidence=None
    if evidence_path.exists():
        evidence=json.loads(evidence_path.read_text(encoding='utf8'))
        if (metadata and metadata.get('evidence_sha256')!=_hash(evidence_path)):
            raise FormatError('Opcode metadata evidence SHA256 mismatch')
        if evidence.get('mapping_sha256')!=_hash(mapping):
            raise FormatError('Opcode evidence SHA256 does not match provided mapping')
    groups=[('<main>',parsed['main'])]+[(bytes.fromhex(x['name_hex']).decode('ascii'),x) for x in parsed['functions']]
    totals=Counter(); summaries=[]; encountered=Counter(); issues=[]; mapped_total=0
    for name,g in groups:
        ops=g['opcodes']; decoded=[]
        for op in ops:
            opcode=choose_opcode(op,mp)
            key=f'{op["index"]%8}:{op["encoded_opcode"]}'
            status='unknown' if opcode is None else 'inferred'
            if evidence is not None:
                status=evidence.get('entries',{}).get(key,{}).get('status',status)
                if status not in ('confirmed','inferred','unknown'):
                    raise FormatError('Invalid confidence status for '+key)
            elif opcode==140:
                status='unknown'  # mapped numeric value, but meaning conflicts with context

            totals[status]+=1
            mapped_total+=int(opcode is not None)
            decoded.append((op,opcode,status,key))
            if opcode is not None:encountered[names.get(str(opcode),f'OP_{opcode}')]+=1
        unknown=[op['index'] for op,code,status,key in decoded if code is None]
        confirmed=sum(status=='confirmed' for _,_,status,_ in decoded)
        summaries.append({'name':name,'instructions':len(ops),'mapped':len(ops)-len(unknown),
            'unknown_indices':unknown,'recognition_fraction':(len(ops)-len(unknown))/len(ops) if ops else 1.0,
            'confirmed_instruction_count':confirmed, 'confirmed_fraction':confirmed/len(ops) if ops else 0.0,
            'inferred_instruction_count':sum(status=='inferred' for _,_,status,_ in decoded)})
        for index in unknown[:25]:
            issues.append(opcode_window(decoded,index,window,name,names))
    total=sum(totals.values())
    return {'serialized_instructions':total,'mapped_instructions':mapped_total,
        'recognition_fraction':mapped_total/total if total else 1.0,
        'confidence_counts':{'confirmed':totals['confirmed'],'inferred':totals['inferred'],'unknown':totals['unknown']},
        'confidence_policy':'No key-level independent reference verification shipped. Mapped keys are inferred; opcode 140 remains semantically unknown.',
        'evidence_sha256':_hash(evidence_path) if evidence else None,
        'mapping_metadata_sha256':_hash(metadata_path) if metadata else None,
        'opcode_mapping_confidence_fraction':totals['confirmed']/total if total else 1.0,

        'group_diagnostics':summaries,'unknown_windows':issues,
        'opcode_name_counts':dict(sorted(encountered.items())),
        'opcode_140_caution':'In PHP 5.2 opcode 140 may denote DECLARE_INHERITED_CLASS; meaning in serialized stream is not confirmed; no reassignment is attempted.'}


def opcode_window(decoded: list, index: int, radius: int, group: str, names: dict) -> dict:
    rows=[]
    for op,code,status,key in decoded[max(0,index-radius):index+radius+1]:
        rows.append({'index':op['index'],'line':op['line'],'raw_encoded_opcode':op['encoded_opcode'],
            'key':key,'mapped_opcode':code,'name':names.get(str(code)) if code is not None else None,
            'confidence':status})
    return {'group':group,'index':index,'expected':'uniquely mapped opcode','found':'unmapped empirical key','window':rows}


def restore_result(source: Path, dictionary: Path, mapping: Path, *, isolate_parser: bool = False) -> RestoreResult:
    audit={'tool_version':__version__,'status':'unsupported','input_sha256':None,
           'dictionary_sha256':None,'mapping_sha256':None,
           'syntax_checked':False,'semantic_equivalence_proven':False,
           'production_ready':False,'round_trip':{'status':'not_run','reason':'PHP 5.2 compile-only native opcode probe is available, but its op_array dump is not the SSG Team serialized input accepted by this decoder; no validated adapter.'}}
    try:
        # The hashes identify the exact inputs, not just their basenames.
        audit['input_sha256']=_hash(source)
        audit['dictionary_sha256']=_hash(dictionary)
        audit['mapping_sha256']=_hash(mapping)
        content=source.read_bytes()
        if b'@Zend;' not in content[:40]:
            audit['status']='not_encoded'
            return RestoreResult(None,audit,'not_encoded','Zend marker absent in first 40 bytes')
        details=inspect(source,dictionary,mapping,isolate_parser=isolate_parser)
        audit.update(details)
        audit['parser_preflight']={'enabled':isolate_parser,'status':'passed' if isolate_parser else 'not_run'}
        code,old=restore_candidate(source,dictionary,mapping,version='v'+__version__.split('.')[0],trace_rules=True)
        audit.update(old)
        audit['tool_version']=__version__
        audit['status']='candidate_generated'
        audit['mapping_sha256']=_hash(mapping)
        audit['dictionary_sha256']=_hash(dictionary)
        audit['input_sha256']=_hash(source)
        actual=Counter()
        for group in audit['groups']:
            actual.update(group.get('decoder_rule_usage',{}))
        audit['rule_usage']=dict(sorted(actual.items()))
        audit['rule_usage_note']='Decoder branches successfully handled in completed restoration groups; counts are not independently validated semantics.'
        sites=[]
        for group in audit['groups']:
            for site in group.get('encoder_call_sites',[]):
                sites.append(dict(site,group=group.get('name')))
        audit['encoder_call_sites']=sites
        audit['encoder_call_count']=len(sites)
        audit['encoder_call_note']=('Calls addressed by an index into the file header_symbols table are '
            'recognised on the Encoder level only. The native opcode number of these positions stays '
            'unresolved and the native opcode map is not rewritten.')
        audit['supported_unary_bool_not']=actual['BOOL_NOT']>0
        audit['supported_simple_at_function_call']=actual['BEGIN_SILENCE']>0 and actual['END_SILENCE']>0 and actual['DO_FCALL_BY_NAME']>0
        audit['syntax_checked']=False
        audit['semantic_equivalence_proven']=False
        audit['production_ready']=False
        return RestoreResult(code,audit,'candidate_generated')
    except (Exception) as exc:
        # Structured failure instead of propagating malformed or unsupported streams.
        audit['status']='unsupported'
        audit['failure']={'type':type(exc).__name__,'message':str(exc)[:1200]}
        match=re.search(r'(?:opcode\s*#|instruction\s*#|\bat\s*#|\[)(\d+)',str(exc),re.I)
        if match:
            audit['failure']['opcode_index']=int(match.group(1))
            audit['failure']['index_precision']='exact_decoder_instruction_on_exception'
        # B012 is a CFG block ordinal, NOT opcode index 12.
        anchor=re.search(r'block\s+(B\d+)',str(exc))
        if anchor:
            block_id=anchor.group(1)
            audit['failure']['cfg_block']=block_id
            group_match=re.search(r'Cannot restore\s+([^:]+):',str(exc))
            group_name=group_match.group(1) if group_match else '<main>'
            try:
                from .cfg import cfg_for_group
                raw=decompress_encoded(source,dictionary.read_bytes())
                if len(raw)==1:
                    parsed=parse_binary(raw[0][1])
                    groups=[('<main>',parsed['main'])]+[(bytes.fromhex(x['name_hex']).decode('ascii'),x) for x in parsed['functions']]
                    g=next((g for name,g in groups if name==group_name),None)
                    if g is not None:
                        mp=json.loads(mapping.read_text(encoding='utf-8'))
                        for op in g['opcodes']:
                            op['decoded_opcode']=choose_opcode(op,mp)
                        cfg=cfg_for_group(group_name,g)
                        block=next((b for b in cfg['basic_blocks'] if b['id']==block_id),None)
                        if block is not None:
                            idx=audit['failure'].get('opcode_index',block['first'])
                            if not block['first']<=idx<=block['last']:
                                idx=block['first']
                                audit['failure'].pop('opcode_index',None)
                            if 'opcode_index' not in audit['failure']:
                                audit['failure']['opcode_index_hint']=idx
                                audit['failure']['index_precision']='CFG block start only (not exact)'
                            audit['failure']['block_start_opcode_index']=block['first']
                            audit['failure']['block_end_opcode_index']=block['last']
                            evidence_path=mapping.with_name('opcode_evidence.json')
                            ev=json.loads(evidence_path.read_text(encoding='utf-8')).get('entries',{}) if evidence_path.exists() else {}
                            rows=[]
                            for op in g['opcodes']:
                                code=choose_opcode(op,mp)
                                key=f'{op["index"]%8}:{op["encoded_opcode"]}'
                                confidence=ev.get(key,{}).get('status','unknown' if code in (None,140) else 'inferred')
                                rows.append((op,code,confidence,key))
                            issue=opcode_window(rows,idx,2,group_name,mp['names'])
                            issue['expected']='Resolved temporaries/calls for locally decodable block'
                            issue['found']=str(exc)[:300]
                            issue['approximate_block_start']='opcode_index' not in audit['failure']
                            audit['failure']['block_window']=issue
            except Exception:
                pass  # Additional diagnostic failure must not replace the original.
        return RestoreResult(None,audit,'unsupported',f'{type(exc).__name__}: {exc}'[:1250])
