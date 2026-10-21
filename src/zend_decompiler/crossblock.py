#!/usr/bin/env python3
"""Conservative, proof-carrying reconstruction of short-circuit boolean joins.

Supports only side-effect-free CV/constant comparisons and BOOL, followed by
JMPNZ_EX/JMPZ_EX chains with an explicit shared target. Other expressions
are left unresolved rather than guessed. Does NOT execute the PHP source.
"""
from __future__ import annotations
import json
from pathlib import Path
from .assets import OPCODE_MAP, DICTIONARY
from .serial_parser import decompress_encoded, parse_binary
from .calibrate import choose_opcode
from .prefix_restore import Decoder, Unsupported, spot
from .cfg import cfg_for_group

COMPARISONS={
    'IS_EQUAL':b' == ', 'IS_NOT_EQUAL':b' != ',
    'IS_SMALLER':b' < ', 'IS_SMALLER_OR_EQUAL':b' <= ',
    'IS_IDENTICAL':b' === ', 'IS_NOT_IDENTICAL':b' !== ',
}


def join_proofs(ops:list[dict], cv:dict[int,bytes], mapping:dict) -> dict[int,dict]:
    """Return verified join summaries keyed by the consuming JMPZ/JMPNZ index."""
    parser=Decoder(ops,cv,mapping)
    def name(index):
        return parser.kind(ops[index])
    def slot(node):
        return spot(node)
    def term_ending_at(index:int, expected):
        """Prove a pure comparison, optionally preceded by single-dimension
        FETCH_DIM_R operands. Require strict adjacency and matching TEMP slots.
        This intentionally rejects calls, nested DIM reads and side effects.
        """
        consumed=[]
        final=ops[index]
        if name(index)=='BOOL':
            if slot(final['result'])!=expected:
                raise Unsupported('BOOL result slot changed')
            expected=slot(final['op1'])
            consumed.append(index)
            index-=1
        op=ops[index]
        if name(index) not in COMPARISONS:
            raise Unsupported('Not a supported comparison')
        if slot(op['result']) != expected:
            raise Unsupported('Comparison result not in expected slot')
        consumed.append(index)
        cursor=index-1
        # Zend evaluates op1 before op2; resolve the last materialized operand
        # first, so each tracked FETCH_DIM_R must be exactly the preceding op.
        values={}
        for key in ('op2','op1'):
            node=op[key]
            if node['type'] in (1,16):
                values[key]=parser.val(node)
                continue
            if node['type'] not in (2,4) or cursor < 0:
                raise Unsupported('Unsupported comparison operand')
            fetch=ops[cursor]
            if name(cursor)!='FETCH_DIM_R' or slot(fetch['result'])!=slot(node):
                raise Unsupported('Unproven FETCH_DIM_R producer')
            if fetch['op1']['type'] not in (1,16) or fetch['op2']['type'] not in (1,16):
                raise Unsupported('Nested or volatile dimension read')
            values[key]=parser.val(fetch['op1'])+b'['+parser.val(fetch['op2'])+b']'
            consumed.append(cursor)
            cursor-=1
        expression=b'('+values['op1']+COMPARISONS[name(index)]+values['op2']+b')'
        return expression,cursor,consumed

    found={}
    for join in range(len(ops)):
        final=ops[join]
        if name(join) not in ('JMPZ','JMPNZ') or final['op1']['type'] not in (2,4):
            continue
        result=slot(final['op1'])
        try:
            last,cursor,included=term_ending_at(join-1,result)
            terms=[last];proof_indices=included[:];shortcuts=[];mode=None
            while cursor>=0 and name(cursor) in ('JMPNZ_EX','JMPZ_EX'):
                jump=ops[cursor];shortcut_kind=name(cursor)
                if jump['op2']['type']!=8 or jump['op2']['word1']!=1 or jump['op2']['word0']!=join:
                    break
                if slot(jump['result'])!=result or slot(jump['op1'])!=result:
                    break
                if mode is not None and shortcut_kind!=mode:
                    break
                mode=shortcut_kind
                expr,cursor2,used=term_ending_at(cursor-1,result)
                terms.insert(0,expr)
                proof_indices.extend(used+[cursor]);shortcuts.append(cursor)
                cursor=cursor2
            if not shortcuts:continue
            glue=b' || ' if mode=='JMPNZ_EX' else b' && '
            composite=b'('+glue.join(terms)+b')'
            found[join]={'join_index':join,
                         'slot':list(result),
                         'mode':'OR' if mode=='JMPNZ_EX' else 'AND',
                         'expression_hex':composite.hex(),
                         'expression':composite.decode('cp1251','backslashreplace'),
                         'comparison_count':len(terms),
                         'source_indices':sorted(set(proof_indices+[join])),
                         'shortcut_indices':sorted(shortcuts),
                         'fallthrough':join+1,
                         'branch_target':final['op2']['word0'],
                         'conditional_opcode':name(join)}
        except (Unsupported, IndexError, KeyError, TypeError):
            continue
    return found


def analyzed_source(source:Path,dict_path:Path,map_path:Path) -> tuple[dict,dict,dict,dict]:
    streams=decompress_encoded(source,dict_path.read_bytes())
    if len(streams)!=1:raise Unsupported('Expected one encoded stream')
    parsed=parse_binary(streams[0][1]);group=parsed['main']
    mapping=json.loads(map_path.read_text())
    for op in group['opcodes']:op['decoded_opcode']=choose_opcode(op,mapping)
    cvs={v['index']:bytes.fromhex(v['name_hex']) for v in group['compiled_vars']}
    return group, mapping, cfg_for_group('main',group),join_proofs(group['opcodes'],cvs,mapping)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('--dictionary',type=Path,default=DICTIONARY)
    p.add_argument('--map',type=Path,default=OPCODE_MAP)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();g,m,c,proofs=analyzed_source(a.source,a.dictionary,a.map)
    a.out.write_text(json.dumps({'file':a.source.name,'total_ops':len(g['opcodes']),
                                 'verified_short_circuit_joins':list(proofs.values())},indent=2,ensure_ascii=False)+'\n')
    print(f'Verified {len(proofs)} cross-block short-circuit joins')
