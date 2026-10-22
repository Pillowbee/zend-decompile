"""Fail-closed PHP 5.2 control-flow state emitter.

Generates a switch/while dispatch loop from a fully decoded, validated CFG. This
is a semantic fallback for reducible/irreducible but *locally decodable* graphs;
it does not fabricate unknown instructions or cross-block temporary values.
"""
from __future__ import annotations

from .cfg import cfg_for_group
from .crossblock import join_proofs
from .calibrate import choose_opcode
from .prefix_restore import Decoder, Unsupported
from .structure import build_graph, insist
from collections import Counter


def recover_blocks(group, mapping, name, symbols=None, callees=None):
    ops=group['opcodes']
    for op in ops:
        op['decoded_opcode']=choose_opcode(op,mapping)
        op['_decoded_name']=mapping['names'].get(str(op['decoded_opcode']))
    unresolved=[op['index'] for op in ops if op['decoded_opcode'] is None]
    insist(not unresolved, f'unknown opcodes at {unresolved[:12]}')
    cvs={x['index']:bytes.fromhex(x['name_hex']) for x in group['compiled_vars']}
    cfg=cfg_for_group(name,group)
    proofs=join_proofs(ops,cvs,mapping)
    blocks=[]
    used_rules=Counter()
    encoder_calls=[]
    for block in cfg['basic_blocks']:
        decoder=Decoder(ops,cvs,mapping,symbols,callees)
        if block['first'] in proofs:
            p=proofs[block['first']]
            decoder.defs[tuple(p['slot'])]=bytes.fromhex(p['expression_hex'])
        try:
            segment=decoder.run(block['first'],block['last'])
        except Unsupported as exc:
            raise Unsupported(f'{name} block {block["id"]} opcode #{decoder.current_index}: {exc}') from exc
        used_rules.update(segment.fired_rules or {})
        encoder_calls.extend(segment.encoder_calls or [])
        blocks.append({
            'id':block['id'],'first':block['first'],'last':block['last'],
            'statements':[s.decode('cp1251') for s in segment.statements],
            'statement_sources':list(segment.statement_sources or []),
            'branch':None if segment.branch is None else {
                'opcode':segment.branch[0],
                'condition':segment.branch[1].decode('cp1251'),
                'target':segment.branch[2]},
            'successors':block['successors']})
    return blocks,proofs,cvs,used_rules,encoder_calls


def _branch_side_effect_suppression(block):
    """Prevent double evaluation of condition assignments already emitted.

    The local Decoder represents an ASSIGN-and-branch condition as *both* a
    statement and expression. Exactly matched assignments are emitted only as
    part of the branch condition. All other statements are retained.
    """
    s=block['statements']
    br=block['branch']
    if not br or not s:return s,False
    expr=br['condition']
    if expr.startswith('(') and expr.endswith(')'):
        raw=expr[1:-1]
        normalized=[line.strip().removesuffix(';') for line in s]
        if len(s)==1 and normalized[0]==raw.strip():
            return [],True
        if raw.strip() in normalized:
            raise Unsupported('Ambiguous inline branch assignment among multiple statements: '+block['id'])
    return s,False


def _unique_state_variable(cvs):
    present={v.decode('latin1') for v in cvs.values()}
    name='_zend_decompiler_pc_v19'
    while name in present:name+='x'
    return '$'+name


def state_emit(group,mapping,name,symbols=None,callees=None):
    blocks,proofs,cvs,used_rules,encoder_calls=recover_blocks(group,mapping,name,symbols,callees)
    kept, graph, folded, removed=build_graph({
        'blocks':blocks,'proven_short_circuit_joins':list(proofs.values())})
    labels=sorted(kept,key=lambda b:kept[b]['first'])
    pc=_unique_state_variable(cvs)
    lines=[pc+" = 'B000';",'while (1) {',f'    switch ({pc}) {{']
    suppressed=[];terminal=[]; edges=0
    for label in labels:
        b=kept[label]
        s,was_suppressed=_branch_side_effect_suppression(b)
        if was_suppressed:suppressed.append(label)
        lines.append(f"        case '{label}':")
        lines.extend('            '+t for t in s)
        succ=b['successors']
        if not succ:
            insist(bool(s) and s[-1].startswith('return '), f'Unknown terminal {label}')
            terminal.append(label)
            continue
        edges+=len(succ)
        if len(succ)==1:
            lines.append(f"            {pc} = '{succ[0]['block']}';")
        elif len(succ)==2:
            br=b['branch']
            insist(br is not None, f'Condition missing at {label}')
            if br['opcode'] in ('JMPZ','JMPNZ'):
                bykind={s['kind']:s['block'] for s in succ}
                insist(set(bykind)=={'zero','nonzero'},f'Invalid branch kinds in {label}')
                yes,no=bykind['nonzero'],bykind['zero']
            elif br['opcode']=='JMPZNZ':
                bykind={s['kind']:s['block'] for s in succ}
                insist(set(bykind)=={'extended','operand2'},f'Invalid ternary branch kinds in {label}')
                yes,no=bykind['extended'],bykind['operand2']
            else:raise Unsupported(f'Unknown 2-way branch at {label}: {br["opcode"]}')
            insist(bool(br['condition']),f'Empty condition at {label}')
            lines.append(f"            if ({br['condition']}) {{")
            lines.append(f"                {pc} = '{yes}';")
            lines.append('            } else {')
            lines.append(f"                {pc} = '{no}';")
            lines.append('            }')
        else:raise Unsupported(f'Unsupported branch fanout {len(succ)} at {label}')
        lines.append('            break;')
    lines.extend(['        default:',
                  "            trigger_error('Invalid recovered control-flow state', E_USER_ERROR);",
                  '            return NULL;',
                  '    }','}'])
    original_in_blocks={idx for b in blocks for idx in range(b['first'],b['last']+1)}
    insist(original_in_blocks==set(range(len(group['opcodes']))),'Source instruction coverage mismatch')
    audit={'strategy':'explicit_php52_state_machine','name':name,
           'source_instruction_count':len(group['opcodes']),
           'decoder_rule_usage':dict(sorted(used_rules.items())),
           'encoder_call_sites':encoder_calls,
           'decoded_basic_blocks':len(blocks),'emitted_state_cases':len(labels),
           'folded_short_circuits':len(folded),
           'excluded_verified_unreachable':len(removed)-sum(1 for f in folded for x in f['removed'] if x in removed),
           'terminal_states':terminal, 'generated_state_edges':edges,
           'suppressed_duplicate_branch_assignments':suppressed,
           'source_cfg_edges':[(a,b) for a,b in graph.edges if b!='EXIT'],
           'unknown_opcodes':[], 'runtime_validation':False,
           'semantic_equivalence_proven':False}
    return lines,audit
