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
from .encoder_calls import declared_callees

COMPARISONS={
    'IS_EQUAL':b' == ', 'IS_NOT_EQUAL':b' != ',
    'IS_SMALLER':b' < ', 'IS_SMALLER_OR_EQUAL':b' <= ',
    'IS_IDENTICAL':b' === ', 'IS_NOT_IDENTICAL':b' !== ',
}
INIT_NAMES={'INIT_FCALL_BY_NAME','INIT_METHOD_CALL','INIT_STATIC_METHOD_CALL'}
CALL_END_NAMES={'DO_FCALL','DO_FCALL_BY_NAME'}
SEND_NAMES={'SEND_VAL','SEND_VAR','SEND_VAR_NO_REF'}


def call_range(ops:list[dict], name, index:int) -> tuple[int,int]:
    """Instruction range of the call that ends at `index`.

    Returns the first and the last instruction of the call, so that the
    whole call can be decoded as one closed segment.
    """
    kind=name(index)
    if kind=='DO_FCALL_BY_NAME':
        for cursor in range(index-1,-1,-1):
            other=name(cursor)
            if other in CALL_END_NAMES:break
            if other in INIT_NAMES:return cursor,index
        raise Unsupported('Call without a visible initializer')
    if kind=='DO_FCALL':
        cursor=index-1
        while cursor>=0 and name(cursor) in SEND_NAMES:cursor-=1
        return cursor+1,index
    raise Unsupported('Not a call terminator')


def render_range(ops:list[dict], cv:dict, mapping:dict, first:int, last:int, slot) -> bytes:
    """Render one expression by decoding a closed instruction range."""
    decoder=Decoder(ops,cv,mapping)
    decoder.run(first,last)
    value=decoder.defs.get(tuple(slot))
    if value is None:raise Unsupported('Unrenderable term range')
    return value


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
        A comparison operand may also be the result of a call; the call is
        then decoded as one closed segment and inlined into the term.
        """
        consumed=[]
        calls=[]
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
            if name(cursor)=='FETCH_DIM_R' and slot(fetch['result'])==slot(node):
                if fetch['op1']['type'] not in (1,16) or fetch['op2']['type'] not in (1,16):
                    raise Unsupported('Nested or volatile dimension read')
                values[key]=parser.val(fetch['op1'])+b'['+parser.val(fetch['op2'])+b']'
                consumed.append(cursor)
                cursor-=1
                continue
            if name(cursor)=='FETCH_R' and slot(fetch['result'])==slot(node) and fetch['op1']['type']==16:
                # A plain read of a compiled variable is pure.
                values[key]=parser.val(fetch['op1'])
                consumed.append(cursor)
                cursor-=1
                continue
            if name(cursor) in CALL_END_NAMES and slot(fetch['result'])==slot(node):
                # A call result may be compared directly.  The call is decoded
                # as one closed segment, so the argument order is preserved.
                first,last=call_range(ops,name,cursor)
                values[key]=render_range(ops,cv,mapping,first,cursor,slot(node))
                calls.append({'index':cursor,'first':first,'last':last})
                cursor=first-1
                continue
            raise Unsupported('Unproven operand producer')
        expression=b'('+values['op1']+COMPARISONS[name(index)]+values['op2']+b')'
        return expression,cursor,consumed,calls

    found={}
    for join in range(len(ops)):
        final=ops[join]
        if name(join) not in ('JMPZ','JMPNZ') or final['op1']['type'] not in (2,4):
            continue
        result=slot(final['op1'])
        try:
            last,cursor,included,calls=term_ending_at(join-1,result)
            terms=[last];proof_indices=included[:];shortcuts=[];mode=None
            call_sites=list(calls)
            while cursor>=0 and name(cursor) in ('JMPNZ_EX','JMPZ_EX'):
                jump=ops[cursor];shortcut_kind=name(cursor)
                if jump['op2']['type']!=8 or jump['op2']['word1']!=1 or jump['op2']['word0']!=join:
                    break
                if slot(jump['result'])!=result or slot(jump['op1'])!=result:
                    break
                if mode is not None and shortcut_kind!=mode:
                    break
                mode=shortcut_kind
                expr,cursor2,used,more_calls=term_ending_at(cursor-1,result)
                terms.insert(0,expr)
                proof_indices.extend(used+[cursor]);shortcuts.append(cursor)
                call_sites.extend(more_calls)
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
                         'call_sites':call_sites,
                         'fallthrough':join+1,
                         'branch_target':final['op2']['word0'],
                         'conditional_opcode':name(join)}
        except (Unsupported, IndexError, KeyError, TypeError):
            continue
    return found


def analyzed_source(source:Path,dict_path:Path,map_path:Path) -> tuple[dict,dict,dict,dict,list,dict]:
    """Parse one encoded file and analyse its main group.

    Returns the group, the mapping, its CFG, the verified joins, the file
    symbol table and the functions declared in the same file.  The last two
    are required by the Encoder level call recognition.
    """
    streams=decompress_encoded(source,dict_path.read_bytes())
    if len(streams)!=1:raise Unsupported('Expected one encoded stream')
    parsed=parse_binary(streams[0][1]);group=parsed['main']
    mapping=json.loads(map_path.read_text())
    for op in group['opcodes']:op['decoded_opcode']=choose_opcode(op,mapping)
    cvs={v['index']:bytes.fromhex(v['name_hex']) for v in group['compiled_vars']}
    symbols=parsed.get('header_symbols',[])
    callees=declared_callees(parsed,mapping)
    return (group, mapping, cfg_for_group('main',group),
            join_proofs(group['opcodes'],cvs,mapping), symbols, callees)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('--dictionary',type=Path,default=DICTIONARY)
    p.add_argument('--map',type=Path,default=OPCODE_MAP)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();g,m,c,proofs,_,_=analyzed_source(a.source,a.dictionary,a.map)
    a.out.write_text(json.dumps({'file':a.source.name,'total_ops':len(g['opcodes']),
                                 'verified_short_circuit_joins':list(proofs.values())},indent=2,ensure_ascii=False)+'\n')
    print(f'Verified {len(proofs)} cross-block short-circuit joins')
