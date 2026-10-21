#!/usr/bin/env python3
"""Single restoration core: PHP 5.2 candidate generation from encoded op arrays.

This module owns all orchestration previously spread over v18/v19/v20.
It never executes supplied PHP. Mappings are empirical; semantic equivalence is NOT proven.
"""
from __future__ import annotations
import hashlib, json
from collections import Counter
from pathlib import Path
from zend_serial_parser import decompress_encoded, parse_binary
from zend_calibrate import choose_opcode
from zend_cfg import cfg_for_group
from zend_crossblock import join_proofs
from zend_prefix_restore import Decoder, Unsupported, sym
from zend_structure import Emitter, build_graph, insist, StructureError
from zend_state import state_emit

def function_parameters(group: dict) -> list[bytes]:
    ops = group['opcodes']
    cv = {v['index']:bytes.fromhex(v['name_hex']) for v in group['compiled_vars']}
    params=[]
    for op in ops:
        if op.get('decoded_opcode') is None:
            break
        # Match numeric name through observation map metadata injected by caller.
        if op.get('_decoded_name')!='RECV':
            break
        n=op['op1'];r=op['result']
        insist(n['type']==1 and n['constant']['kind']=='integer' and
               n['constant']['value']==len(params)+1, 'Nonsequential RECV arguments')
        insist(r['type']==16 and r['word0'] in cv, 'Parameter CV missing')
        params.append(b'$'+sym(cv[r['word0']]))
    return params

def build_group(group: dict, mapping: dict, name: str):
    ops = group['opcodes']
    for op in ops:
        op['decoded_opcode'] = choose_opcode(op, mapping)
        op['_decoded_name'] = mapping['names'].get(str(op['decoded_opcode']))
    unresolved = [op['index'] for op in ops if op['decoded_opcode'] is None]
    insist(not unresolved, f'{name}: unknown opcodes at {unresolved[:15]}')
    cvs = {v['index']: bytes.fromhex(v['name_hex']) for v in group['compiled_vars']}
    cfg = cfg_for_group(name, group)
    proofs = join_proofs(ops, cvs, mapping)
    blocks = []
    used_rules=Counter()
    for b in cfg['basic_blocks']:
        d = Decoder(ops, cvs, mapping)
        if b['first'] in proofs:
            proof = proofs[b['first']]
            d.defs[tuple(proof['slot'])] = bytes.fromhex(proof['expression_hex'])
        try:
            res = d.run(b['first'], b['last'])
        except Unsupported as e:
            raise Unsupported(f'{name} block {b["id"]} opcode #{d.current_index}: {e}') from e
        used_rules.update(res.fired_rules or {})
        blocks.append({
            'id': b['id'], 'first': b['first'], 'last': b['last'],
            'statements': [line.decode('cp1251') for line in res.statements],
            'branch': None if res.branch is None else {'opcode': res.branch[0],
                'condition': res.branch[1].decode('cp1251'), 'target': res.branch[2]},
            'successors': b['successors']
        })
    data = {'source': name, 'total':len(ops), 'blocks':blocks,
            'proven_short_circuit_joins':list(proofs.values())}
    kept, graph, folded, removed = build_graph(data)
    emitter=Emitter(kept, graph, folded, removed)
    generated, audit=emitter.generate(len(ops))
    # The generic structurer emits a top-level PHP header; the calling wrapper
    # decides whether to use this fragment as top-level code or function body.
    # IMPORTANT: never use splitlines() here: multiline PHP literals contain
    # significant CRLF bytes which splitlines() silently normalizes.
    lines=emitter.lines
    assert lines[0]=='<?php' and lines[1].startswith('/*')
    last_comment=lines.index(' */')
    body=lines[last_comment+1:]
    audit['name'] = name
    audit['decoder_rule_usage'] = dict(sorted(used_rules.items()))
    audit['source_cfg_blocks'] = len(blocks)
    audit['decoder'] = 'empirical_mapping_php52'
    audit['unknown_opcodes'] = unresolved
    audit['output_syntax_passed'] = None
    return body, audit

def function_parameters_after_decode(group,mapping):
    from zend_calibrate import choose_opcode
    for op in group['opcodes']:
        op['decoded_opcode']=choose_opcode(op,mapping)
        op['_decoded_name']=mapping['names'].get(str(op['decoded_opcode']))
    return [p.decode('ascii') for p in function_parameters(group)]

def restore(encoded,dictionary,mapping_file, *, version="v28", trace_rules=False):
    streams=decompress_encoded(encoded,dictionary.read_bytes())
    insist(len(streams)==1,'Multiple encoded streams unsupported')
    parsed=parse_binary(streams[0][1]);mapping=json.loads(mapping_file.read_text(encoding="utf-8"))
    groups=[('<main>',parsed['main'])]+[(bytes.fromhex(f['name_hex']).decode('ascii'),f) for f in parsed['functions']]
    body_parts=[];audit_groups=[]
    for name,group in groups:
        params=[] if name=='<main>' else function_parameters_after_decode(group,mapping)
        try:
            lines,audit=build_group(group,mapping,name)
            audit['strategy']='structured_php'
        except (StructureError,Unsupported,ValueError) as exc:
            try:
                lines,audit=state_emit(group,mapping,name)
                audit['structured_failure']=str(exc)
            except (StructureError,Unsupported,ValueError) as fallback_exc:
                raise Unsupported(f'Cannot restore {name}: structured: {exc}; state fallback: {fallback_exc}') from fallback_exc
        if not trace_rules:
            audit.pop('decoder_rule_usage',None)  # v20 golden audit schema is immutable.
        audit_groups.append(audit)
        if name=='<main>':body_parts.extend(lines)
        else:
            insist(name.isidentifier(),f'Invalid function name {name!r}')
            body_parts.extend(['',f'function {name}('+', '.join(params)+') {',
                               *['    '+line for line in lines],'}'])
    output=['<?php',f'/* EXPERIMENTAL Zend recovery {version}. Verify before use. */',*body_parts,'']
    report={'version':version,'source':encoded.name,
        'source_sha256':hashlib.sha256(encoded.read_bytes()).hexdigest(),
        'autogenerated_from_encoded_binary':True,'used_preexisting_php_candidate':False,
        'groups':audit_groups,'total_serialized_instructions':sum(len(x['opcodes']) for _,x in groups),
        'syntax_checked':False,'semantic_equivalence_proven':False,'production_ready':False}
    return '\n'.join(output).encode('cp1251'),report

