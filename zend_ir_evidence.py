#!/usr/bin/env python3
"""Offline evidence for source-revision correlation and potential CFG joins.

NO PHP execution, generated PHP, Zend extensions, or promotion of Encoder
mappings. Every opcode name is a *historical hypothesis*; source correlation
is not a replacement for an independently verified Encoder/native oracle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from zend_assets import OPCODE_MAP, DICTIONARY

from zend_calibrate import choose_opcode
from zend_cfg import JMPZ_EX, JMPNZ_EX, branch_destinations
from zend_readonly_dataflow import read_definitions, _validated_evidence
from zend_serial_parser import parse_binary, decompress_encoded


PHP_TAG = re.compile(r'<\?(?:php\b|=)?|\?>', re.I)
FUNCTION = re.compile(r'\bfunction\s+([A-Za-z_][A-Za-z_0-9]*)\s*\(', re.I)
FOREACH = re.compile(r'\bforeach\s*\(', re.I)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def php_mask(src: str) -> str:
    """Filter inline HTML and JavaScript, preserving character offsets.

    Suitable for source *hints* only. This is not a complete PHP lexer and
    is never used to certify equivalence or to generate PHP.
    """
    buf = [' '] * len(src)
    php = False
    pos = 0
    for match in PHP_TAG.finditer(src):
        if php:
            buf[pos:match.start()] = src[pos:match.start()]
        php = match.group() != '?>'
        pos = match.end()
    if php:
        buf[pos:] = src[pos:]
    return ''.join(buf)


def strip_php_comments_and_strings(masked_php: str) -> str:
    """Mask comments/string tokens for approximate code-keyword detection.

    This small lexer intentionally does not attempt to parse PHP heredocs or
    interpolate variable expressions; output remains only lexical evidence.
    """
    out=list(masked_php)
    i=0;n=len(masked_php);state='code'
    while i<n:
        c=masked_php[i]
        following=masked_php[i+1] if i+1<n else ''
        if state=='code':
            if c in ("'", '\"'):
                state=c;out[i]=' '
            elif c=='/' and following=='*':
                state='block';out[i]=out[i+1]=' ';i+=1
            elif c=='/' and following=='/':
                state='line';out[i]=out[i+1]=' ';i+=1
            elif c=='#':
                state='line';out[i]=' '
        elif state in ("'", '\"'):
            if c=='\\':
                out[i]=' '
                if i+1<n:out[i+1]=' ';i+=1
            elif c==state:
                out[i]=' ';state='code'
            elif c!='\n':out[i]=' '
        elif state=='block':
            if c=='*' and following=='/':
                out[i]=out[i+1]=' ';i+=1;state='code'
            elif c!='\n':out[i]=' '
        elif state=='line':
            if c=='\n':state='code'
            else:out[i]=' '
        i+=1
    return ''.join(out)


def source_hints(source: Path) -> dict:
    """Surface approximate function spans, explicitly only source anchors.

    A lexical segment extends to the next function declaration, so its
    `foreach` count is a hint and may include top-level code or comments.
    We report no source code or string literal content.
    """
    blob = source.read_bytes()
    code = strip_php_comments_and_strings(php_mask(blob.decode('cp1251', errors='strict')))
    matches = list(FUNCTION.finditer(code))
    by_name = {}
    for index, match in enumerate(matches):
        end = matches[index+1].start() if index+1 < len(matches) else len(code)
        segment=code[match.start():end]
        name=match.group(1).lower()
        if name in by_name:
            raise ValueError(f'Duplicate PHP function {name} in source {source.name}')
        by_name[name] = {
            'source_start_line':code.count('\n',0,match.start())+1,
            'possible_foreach_keyword_count':len(FOREACH.findall(segment)),
            'contains_foreach_keyword':bool(FOREACH.search(segment)),
            'span_method':'until_next_PHP_function_declaration; lexical hint only',
        }
    return {'filename':source.name,'sha256':hashlib.sha256(blob).hexdigest(),
            'encoding':'cp1251','function_count_lexical':len(matches),
            'functions':by_name}


def encoded_key(op:dict) -> str:
    return f'{op["index"] % 8}:{op["encoded_opcode"]}'


def operand_shape(op:dict)-> tuple:
    return tuple(op[k]['type'] for k in ('result','op1','op2'))


def neighborhood(ops:list[dict], position:int, radius:int=2)->dict:
    """Literal-free context fingerprint, specific to an opcode *position*."""
    if not 0<=position<len(ops):
        raise ValueError('position outside opcode array')
    if radius<0:raise ValueError('negative radius')
    offsets=[]
    for displacement in range(-radius,radius+1):
        idx=position+displacement
        if 0<=idx<len(ops):
            op=ops[idx]
            offsets.append({'relative_instruction':displacement,'key':encoded_key(op),
                            'types':list(operand_shape(op))})
        else:
            offsets.append({'relative_instruction':displacement,'absent':True})
    canonical=json.dumps(offsets,sort_keys=True,separators=(',',':'))
    return {'window':offsets,'fingerprint_sha256':hashlib.sha256(canonical.encode()).hexdigest()}


def unknown_contexts(parsed:dict, mapping:dict, evidence:dict, source_hints_by_name:dict)->list[dict]:
    seen=[]
    for group in parsed['functions']:
        name=bytes.fromhex(group['name_hex']).decode('cp1251').lower()
        for op in group['opcodes']:
            key=encoded_key(op)
            row=evidence.get(key)
            if choose_opcode(op,mapping) is not None and row and row.get('status')!='unknown':
                continue
            ctx=neighborhood(group['opcodes'],op['index'])
            seen.append({'function':name,'index':op['index'], 'key':key,
                        'evidence_status':row.get('status') if row else 'missing',
                        'opcode_confirmed':False,
                        **ctx,
                        'plaintext_function_hints':{
                            path:{'function_present':name in hints['functions'],
                                  'foreach_keyword':hints['functions'].get(name,{}).get('contains_foreach_keyword',False),
                                  'source_start_line':hints['functions'].get(name,{}).get('source_start_line')}
                            for path,hints in source_hints_by_name.items()}})
    return seen


def short_circuit_candidates(group:dict)->list[dict]:
    """Recognize a proven *structural* CFG split/merge, not PHP semantics.

    Guard: a JMP*_EX defines TMP/VAR slot K, the fallthrough arm ends
    with a BOOL writing K, and the other arm jumps directly to a read
    of K. Both producers must have independently reproducible CFG paths.
    No computation of `&&` or `||` is performed here.
    """
    ops=group['opcodes']; report=read_definitions(group)
    if report['status']!='analyzed_syntactically':return []
    by_read=defaultdict(list)
    for read in report['temporary_uses']:
        by_read[read['instruction_index']].append(read)
    patterns=[]
    for op in ops:
        i=op['index']
        if op['decoded_opcode'] not in (JMPZ_EX,JMPNZ_EX):continue
        result=op['result']
        if result['type'] not in (2,4):continue
        slot=(result['type'],result['word0'],result['word1'])
        try:
            branches=branch_destinations(op,len(ops))
        except ValueError:continue
        if len(branches)!=2:continue
        jump_target=branches[0][0]
        fallthrough=branches[1][0]
        if not (fallthrough==i+1 and i+1<jump_target<len(ops)):
            continue
        # Last instruction before the join must produce the same TMP via BOOL.
        bool_idx=jump_target-1
        bool_op=ops[bool_idx]
        bool_result=bool_op['result']
        if bool_op['decoded_opcode']!=52 or bool_result['type']!=result['type'] or (bool_result['word0'],bool_result['word1'])!=(result['word0'],result['word1']):
            continue
        # The BOOL arm must be reachable in a straight line from i+1;
        # nested jumps are not modeled by this narrow recognizer.
        if any(x['decoded_opcode'] in (42,43,44,45,46,47,50,51,62,77,78,79,107,108,149) for x in ops[i+1:bool_idx]):
            continue
        for row in by_read.get(jump_target,[]):
            if tuple(row['slot'])!=slot or sorted(row['reaching_definition_indices'])!=[i,bool_idx]:
                continue
            witness=row.get('structural_path_witnesses',{})
            if witness.get('status')!='complete' or {w['definition_index'] for w in witness.get('witnesses',[])}!={i,bool_idx}:
                continue
            patterns.append({
                'kind':'POTENTIAL_SHORT_CIRCUIT_PHI_NOT_SEMANTICALLY_VERIFIED',
                'jump_instruction':i,'jump_native_hypothesis':op['decoded_opcode'],
                'boolean_instruction':bool_idx,'join_instruction':jump_target,
                'join_operand':row['operand'],'slot':list(slot),
                'reaching_definition_indices':[i,bool_idx],
                'structural_path_witnesses':witness.get('witnesses',[]),
                'semantic_equivalence_proven':False,
                'emit_php_permitted':False})
    return patterns


def produce(encoded:Path, sources:list[Path], dictionary:Path, mapping_file:Path)->dict:
    evidence=_validated_evidence(mapping_file)
    mapping=json.loads(mapping_file.read_text(encoding='utf-8'))
    streams=decompress_encoded(encoded,dictionary.read_bytes())
    if len(streams)!=1:raise ValueError('Expected one encoded stream; refusing ambiguous input')
    parsed=parse_binary(streams[0][1])
    hints={p.name:source_hints(p) for p in sources}
    context=unknown_contexts(parsed,mapping,evidence,hints)
    groups=[]
    for grp in parsed['functions']:
        name=bytes.fromhex(grp['name_hex']).decode('cp1251')
        for op in grp['opcodes']:
            op['decoded_opcode']=choose_opcode(op,mapping)
            k=encoded_key(op)
            if evidence.get(k,{}).get('status')=='unknown':
                op['decoded_opcode']=None
        patterns=short_circuit_candidates(grp)
        if patterns:
            groups.append({'group':name,'join_candidates':patterns})
    clusters=defaultdict(list)
    for observation in context:
        clusters[(observation['key'],observation['fingerprint_sha256'])].append(
            {'function':observation['function'],'instruction':observation['index']})
    repeated=[{'encoded_key':key,'fingerprint_sha256':fingerprint,'occurrences':sorted(v,key=lambda x:(x['function'],x['instruction'])),
               'status':'REPEATED_ENCODED_SHAPE_NOT_NATIVE_OPCODE_PROOF'}
              for (key,fingerprint),v in sorted(clusters.items()) if len(v)>1]
    return {
        'kind':'READ_ONLY_SOURCE_ANCHORED_IR_EVIDENCE_V28',
        'encoded':{'filename':encoded.name,'sha256':sha(encoded),
                   'functions_in_table':len(parsed['functions'])},
        'mapping_sha256':sha(mapping_file),'dictionary_sha256':sha(dictionary),
        'sources':{name:{k:v for k,v in doc.items() if k!='functions'} for name,doc in hints.items()},
        'unknown_and_disputed_contexts':context,
        'repeated_neighborhood_shapes':repeated,
        'possible_short_circuit_joins':groups,
        'no_php_executed':True,'php_generated':False,'opcode_mapping_modified':False,
        'semantic_equivalence_proven':False,
        'limits':['Reference revisions are not proven identical to encoded input.',
                  'Source lexer does not parse heredocs, namespaced functions or dynamic PHP constructs; source statistics are hints.',
                  'Opcode meanings and short-circuit branch polarities are historical hypotheses.',
                  'CFG path witnesses are structural; path feasibility is not proven.',
                  'Repetition of an opcode fingerprint does NOT verify native opcode semantics.']}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('encoded',type=Path)
    cli.add_argument('source_revisions',type=Path,nargs='*')
    cli.add_argument('--dictionary',type=Path,default=DICTIONARY)
    cli.add_argument('--map',type=Path,default=OPCODE_MAP)
    cli.add_argument('-o','--output',type=Path,required=True)
    args=cli.parse_args()
    doc=produce(args.encoded,args.source_revisions,args.dictionary,args.map)
    args.output.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'contexts':len(doc['unknown_and_disputed_contexts']),
                      'repeated_shapes':len(doc['repeated_neighborhood_shapes']),
                      'short_circuit_groups':len(doc['possible_short_circuit_joins'])}))


if __name__=='__main__':
    main()
