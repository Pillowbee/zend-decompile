#!/usr/bin/env python3
"""Conservative, proof-carrying reconstruction of short-circuit boolean joins.

Supports CV/constant comparisons, bounded nested dimension reads, a
three-call AND chain, and one assigned call in a checked loop condition.
Other expressions are left unresolved rather than guessed. Does NOT execute PHP.
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
from .readonly_dataflow import _validated_evidence, read_definitions

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


def proof_seeds_by_block(proofs:dict[int,dict], blocks:list[dict]) -> dict[int,dict]:
    """Place proven expression values only at their checked block entries."""
    seeds={}
    for join,proof in proofs.items():
        block=next((b for b in blocks if b['first']<=join<=b['last']),None)
        if block is None:raise Unsupported('Short-circuit join has no CFG block')
        if (proof.get('nested') or proof.get('nested_dimension_reads') or
                proof.get('loop_assignment_join')) and block['first']!=join:
            raise Unsupported('Nested short-circuit join is not at a block entry')
        values={tuple(term['slot']):bytes.fromhex(term['value_hex'])
                for term in proof.get('term_slots',[])}
        values[tuple(proof['slot'])]=bytes.fromhex(proof['expression_hex'])
        existing=seeds.setdefault(block['first'],{})
        for slot,value in values.items():
            if slot in existing and existing[slot]!=value:
                raise Unsupported('Conflicting short-circuit block seed')
            existing[slot]=value
        for extra in proof.get('block_seeds',[]):
            index=extra['instruction_index']
            target=next((b for b in blocks if b['first']<=index<=b['last']),None)
            if target is None or target['first']!=index:
                raise Unsupported('Proven intermediate value is not at a block entry')
            slot=tuple(extra['slot'])
            value=bytes.fromhex(extra['value_hex'])
            existing=seeds.setdefault(index,{})
            if slot in existing and existing[slot]!=value:
                raise Unsupported('Conflicting short-circuit block seed')
            existing[slot]=value
    return seeds


def prove_cv_or_join(ops:list[dict], cv:dict[int,bytes], mapping:dict,
                     join:int) -> dict:
    """Prove the exact CV || CV diamond consumed by a following branch.

    Only the two reads and the shortcut are folded. Earlier statements in
    the lead block stay in place, and the temporary must be overwritten
    immediately after the consuming branch.
    """
    if join<2 or join+1>=len(ops):
        raise Unsupported('CV OR join is out of range')
    first,second,final=ops[join-2:join+1]
    def kind(op):
        return mapping['names'].get(str(choose_opcode(op,mapping)))
    if [kind(op) for op in (first,second,final)]!=['JMPNZ_EX','BOOL','JMPZ']:
        raise Unsupported('Different CV OR condition')
    if (first['op1']['type']!=16 or second['op1']['type']!=16 or
            first['op1']['word0'] not in cv or second['op1']['word0'] not in cv or
            first['result']['type']!=2 or second['result']!=first['result'] or
            final['op1']!=first['result'] or final['result']['type']!=8 or
            first['op2']!={'type':8,'word0':join,'word1':1} or
            final['op2']['type']!=8 or final['op2']['word1']!=1 or
            final['op2']['word0']<=join or
            ops[join+1]['result']!=first['result'] or
            any(op['extended_value']!=0 for op in (first,second,final))):
        raise Unsupported('CV OR operands, slots or targets differ')
    checked=[dict(op,decoded_opcode=choose_opcode(op,mapping)) for op in ops]
    cfg=cfg_for_group('<CV OR join>',{'opcodes':checked,'compiled_vars':[],
                                    'loop_records':[]})
    lead=next((b for b in cfg['basic_blocks'] if b['last']==join-2),None)
    middle=next((b for b in cfg['basic_blocks'] if b['first']==join-1),None)
    tail=next((b for b in cfg['basic_blocks'] if b['first']==join),None)
    if (not all((lead,middle,tail)) or
            not all(b['reachable'] for b in (lead,middle,tail)) or
            middle['last']!=join-1 or tail['last']!=join or
            middle['predecessors']!=[lead['id']] or
            set(tail['predecessors'])!={lead['id'],middle['id']} or
            {(e['kind'],e['block']) for e in lead['successors']}!=
                {('nonzero',tail['id']),('zero',middle['id'])} or
            middle['successors']!=[{'block':tail['id'],'kind':'fallthrough',
                                    'target_instruction':join}]):
        raise Unsupported('CV OR diamond has another entry or edge')
    left=b'$'+cv[first['op1']['word0']]
    right=b'$'+cv[second['op1']['word0']]
    expression=b'('+left+b' || '+right+b')'
    wrapped=b'((bool) '+right+b')'
    return {'join_index':join,'slot':list(spot(first['result'])),'mode':'OR',
            'expression_hex':expression.hex(),
            'expression':expression.decode('cp1251','backslashreplace'),
            'comparison_count':2,'source_indices':[join-2,join-1,join],
            'shortcut_indices':[join-2],'call_sites':[],
            'term_slots':[{'slot':list(spot(second['result'])),
                           'value_hex':wrapped.hex()}],
            'rendered_term':wrapped.decode('cp1251','backslashreplace'),
            'fallthrough':join+1,'branch_target':final['op2']['word0'],
            'conditional_opcode':'JMPZ'}


def join_proofs(ops:list[dict], cv:dict[int,bytes], mapping:dict) -> dict[int,dict]:
    """Return verified join summaries keyed by the consuming JMPZ/JMPNZ index."""
    parser=Decoder(ops,cv,mapping)
    def name(index):
        # An instruction without a known native opcode cannot take part in a
        # proven short circuit; it is skipped instead of failing the group.
        try:
            return parser.kind(ops[index])
        except Unsupported:
            return None
    def slot(node):
        return spot(node)
    def nested_dimension_join(join:int, evidence:dict) -> dict:
        """Prove the observed two-read AND form without moving a dimension read.

        Only CV bases/keys, one exact nine-instruction diamond, confirmed native
        handlers, and closed reaching definitions are accepted. A dimension read
        may be observable, so each term is rendered in its original branch.
        """
        start=join-8
        if start<0 or [name(i) for i in range(start,join+1)]!=[
                'FETCH_DIM_R','FETCH_DIM_R','IS_NOT_EQUAL','JMPZ_EX',
                'FETCH_DIM_R','FETCH_DIM_R','IS_NOT_EQUAL','BOOL','JMPZ']:
            raise Unsupported('Different dimension condition')
        for i in range(start,join+1):
            op=ops[i];key=f'{i%8}:{op["encoded_opcode"]}'
            observed=evidence.get(key)
            if (observed is None or observed.get('status')!='confirmed' or
                    observed.get('opcode')!=op.get('decoded_opcode') or
                    mapping['opcodes'].get(key)!=op.get('decoded_opcode') or
                    op['extended_value']!=0):
                raise Unsupported('Dimension condition lacks confirmed opcode')
        first,outer,compare,shortcut,second,outer2,compare2,wrapper,final=(
            ops[i] for i in range(start,join+1))
        def same(left,right):
            return left==right
        def read_pair(inner,container,comparison):
            if (inner['op1']['type']!=16 or inner['op2']['type']!=16 or
                    inner['result']['type']!=4 or container['op1']['type']!=16 or
                    container['op2']['type']!=4 or container['result']['type']!=4 or
                    not same(container['op2'],inner['result']) or
                    comparison['op1']['type']!=4 or
                    not same(comparison['op1'],container['result']) or
                    comparison['op2']['type']!=1 or
                    comparison['op2']['constant']['kind']!='string' or
                    comparison['result']['type']!=2):
                raise Unsupported('Unproven dimension read operands')
        read_pair(first,outer,compare)
        read_pair(second,outer2,compare2)
        if (not same(first['op1'],second['op1']) or
                not same(first['op2'],second['op2']) or
                not same(outer['op1'],outer2['op1']) or
                same(compare['op2'],compare2['op2']) or
                shortcut['op1']['type']!=2 or shortcut['result']['type']!=2 or
                not same(shortcut['op1'],compare['result']) or
                not same(shortcut['result'],compare['result']) or
                shortcut['op2']!={'type':8,'word0':join,'word1':1} or
                wrapper['op1']['type']!=2 or wrapper['result']['type']!=2 or
                not same(wrapper['op1'],compare2['result']) or
                not same(wrapper['result'],shortcut['result']) or
                final['op1']['type']!=2 or
                not same(final['op1'],shortcut['result']) or
                final['result']['type']!=8 or final['op2']['type']!=8 or
                final['op2']['word1']!=1 or
                final['op2']['word0'] in range(start,join+1)):
            raise Unsupported('Unproven dimension join slots or target')
        # The shortcut must skip exactly the second read. No other path may
        # enter the second term or its join from outside this diamond.
        checked=[dict(op,decoded_opcode=choose_opcode(op,mapping)) for op in ops]
        group={'opcodes':checked,'compiled_vars':[],'loop_records':[]}
        cfg=cfg_for_group('<dimension join>',group)
        by_first={b['first']:b for b in cfg['basic_blocks']}
        lead=by_first.get(start);middle=by_first.get(start+4);tail=by_first.get(join)
        if (lead is None or middle is None or tail is None or
                not all(b['reachable'] for b in (lead,middle,tail)) or
                lead['last']!=start+3 or middle['last']!=join-1 or
                tail['last']!=join or middle['predecessors']!=[lead['id']] or
                set(tail['predecessors'])!={lead['id'],middle['id']} or
                {(e['kind'],e['block']) for e in lead['successors']}!=
                    {('zero',tail['id']),('nonzero',middle['id'])} or
                [(e['kind'],e['block']) for e in middle['successors']]!=
                    [('fallthrough',tail['id'])]):
            raise Unsupported('Dimension join has another entry or branch')
        analysis=read_definitions(group,title='<dimension join>')
        if analysis['status']!='analyzed_syntactically':
            raise Unsupported('Dimension join lacks reaching-definition proof')
        expected={(start+1,'op2'):{start},(start+2,'op1'):{start+1},
                  (start+3,'op1'):{start+2},(start+5,'op2'):{start+4},
                  (start+6,'op1'):{start+5},(start+7,'op1'):{start+6},
                  (join,'op1'):{start+3,start+7}}
        seen=set();producers=set(range(start,join))
        for use in analysis['temporary_uses']:
            definitions=set(use['reaching_definition_indices'])
            if not definitions & producers:continue
            key=(use['instruction_index'],use['operand'])
            if key not in expected or definitions!=expected[key]:
                raise Unsupported('Dimension read has an external consumer')
            seen.add(key)
        if seen!=set(expected):
            raise Unsupported('Dimension join has missing producer links')
        left=render_range(ops,cv,mapping,start,start+2,slot(compare['result']))
        right=render_range(ops,cv,mapping,start+4,start+6,slot(compare2['result']))
        rendered=render_range(ops,cv,mapping,start+4,start+7,slot(wrapper['result']))
        expression=b'('+left+b' && '+right+b')'
        return {'join_index':join,'slot':list(slot(final['op1'])),'mode':'AND',
                'expression_hex':expression.hex(),
                'expression':expression.decode('cp1251','backslashreplace'),
                'comparison_count':2,'source_indices':list(range(start,join+1)),
                'shortcut_indices':[start+3],'call_sites':[],
                'term_slots':[{'slot':list(slot(wrapper['result'])),
                               'value_hex':rendered.hex()}],
                'rendered_term':rendered.decode('cp1251','backslashreplace'),
                'fallthrough':join+1,'branch_target':final['op2']['word0'],
                'conditional_opcode':'JMPZ','nested_dimension_reads':True}
    def three_call_and(join:int, evidence:dict) -> dict:
        """Prove three ordered calls joined by two false shortcuts."""
        if (name(join)!='JMPZ' or join<9 or name(join-1)!='BOOL' or
                name(join-2)!='DO_FCALL_BY_NAME'):
            raise Unsupported('Different call condition')
        third_first,_=call_range(ops,name,join-2)
        second_jump=third_first-1
        if (second_jump<3 or name(second_jump)!='JMPZ_EX' or
                name(second_jump-1)!='BOOL' or
                name(second_jump-2)!='BOOL_NOT' or
                name(second_jump-3)!='DO_FCALL_BY_NAME'):
            raise Unsupported('Second call condition absent')
        second_first,_=call_range(ops,name,second_jump-3)
        first_jump=second_first-1
        if (first_jump<2 or name(first_jump)!='JMPZ_EX' or
                name(first_jump-1)!='BOOL_NOT' or
                name(first_jump-2)!='DO_FCALL_BY_NAME'):
            raise Unsupported('First call condition absent')
        first_first,_=call_range(ops,name,first_jump-2)
        calls=[(first_first,first_jump-2),(second_first,second_jump-3),
               (third_first,join-2)]
        permitted={'INIT_FCALL_BY_NAME','DO_FCALL_BY_NAME','CONCAT',
                   'INIT_STRING','ADD_STRING','ADD_VAR','SEND_VAL','SEND_VAR',
                   'SEND_VAR_NO_REF'}
        for first,last in calls:
            kinds=[name(i) for i in range(first,last+1)]
            if (kinds[0]!='INIT_FCALL_BY_NAME' or
                    kinds.count('INIT_FCALL_BY_NAME')!=1 or
                    kinds.count('DO_FCALL_BY_NAME')!=1 or
                    kinds[-1]!='DO_FCALL_BY_NAME' or
                    not set(kinds)<=permitted):
                raise Unsupported('Call interval has other effects')
        first_call,second_call,third_call=(ops[last] for _,last in calls)
        not1,not2,bool2,bool3=(ops[i] for i in
                               (first_jump-1,second_jump-2,second_jump-1,join-1))
        jump1,jump2,final=ops[first_jump],ops[second_jump],ops[join]
        shared=slot(jump1['result'])
        if (first_call['result']['type']!=4 or second_call['result']['type']!=4 or
                third_call['result']['type']!=4 or
                not1['op1']!=first_call['result'] or
                not2['op1']!=second_call['result'] or
                bool2['op1']!=not2['result'] or
                bool3['op1']!=third_call['result'] or
                not1['result']['type']!=2 or not2['result']['type']!=2 or
                bool2['result']['type']!=2 or bool3['result']['type']!=2 or
                final['op1']['type']!=2 or
                any(slot(op['result'])!=shared for op in
                    (not1,jump1,bool2,jump2,bool3)) or
                jump1['op1']!=not1['result'] or
                jump2['op1']!=bool2['result'] or
                final['op1']!=bool3['result'] or
                any(op['op2']!={'type':8,'word0':join,'word1':1}
                    for op in (jump1,jump2)) or
                any(op['extended_value']!=0 for op in
                    (not1,not2,bool2,bool3,jump1,jump2,final)) or
                final['op2']['type']!=8 or final['op2']['word1']!=1 or
                final['op2']['word0'] in range(first_first,join+1)):
            raise Unsupported('Call join slots or targets disagree')
        for i in range(first_first,join+1):
            op=ops[i];key=f'{i%8}:{op["encoded_opcode"]}'
            observed=evidence.get(key)
            if (observed is None or observed.get('status')!='confirmed' or
                    observed.get('opcode')!=op.get('decoded_opcode') or
                    mapping['opcodes'].get(key)!=op.get('decoded_opcode')):
                raise Unsupported('Call condition lacks confirmed opcode')
        group={'opcodes':[dict(op,decoded_opcode=choose_opcode(op,mapping))
                          for op in ops],'compiled_vars':[],'loop_records':[]}
        cfg=cfg_for_group('<call join>',group)
        by_first={b['first']:b for b in cfg['basic_blocks']}
        lead=next((b for b in cfg['basic_blocks'] if b['last']==first_jump),None)
        middle=by_first.get(second_first);last=by_first.get(third_first)
        tail=by_first.get(join)
        if (lead is None or middle is None or last is None or tail is None or
                not all(b['reachable'] for b in (lead,middle,last,tail)) or
                not lead['first']<=first_first or middle['last']!=second_jump or
                last['last']!=join-1 or tail['last']!=join or
                middle['predecessors']!=[lead['id']] or
                last['predecessors']!=[middle['id']] or
                set(tail['predecessors'])!={lead['id'],middle['id'],last['id']} or
                {(e['kind'],e['block']) for e in lead['successors']}!=
                    {('zero',tail['id']),('nonzero',middle['id'])} or
                {(e['kind'],e['block']) for e in middle['successors']}!=
                    {('zero',tail['id']),('nonzero',last['id'])} or
                [(e['kind'],e['block']) for e in last['successors']]!=
                    [('fallthrough',tail['id'])]):
            raise Unsupported('Call join has another entry or branch')
        analysis=read_definitions(group,title='<call join>')
        if analysis['status']!='analyzed_syntactically':
            raise Unsupported('Call join lacks reaching definitions')
        expected={(first_jump-1,'op1'):{calls[0][1]},
                  (first_jump,'op1'):{first_jump-1},
                  (second_jump-2,'op1'):{calls[1][1]},
                  (second_jump-1,'op1'):{second_jump-2},
                  (second_jump,'op1'):{second_jump-1},
                  (join-1,'op1'):{calls[2][1]},
                  (join,'op1'):{first_jump,second_jump,join-1}}
        producers={calls[0][1],first_jump-1,first_jump,
                   calls[1][1],second_jump-2,second_jump-1,second_jump,
                   calls[2][1],join-1}
        uses=[u for u in analysis['temporary_uses']
              if set(u['reaching_definition_indices']) & producers]
        if (len(uses)!=len(expected) or
                {(u['instruction_index'],u['operand']):
                 set(u['reaching_definition_indices']) for u in uses}!=expected):
            raise Unsupported('Call condition has external TMP consumers')
        expressions=[render_range(ops,cv,mapping,first,last,
                                  slot(ops[last]['result'])) for first,last in calls]
        expression=(b'((!'+expressions[0]+b') && (!'+expressions[1]+b') && '+
                    expressions[2]+b')')
        return {'join_index':join,'slot':list(shared),'mode':'AND',
                'expression_hex':expression.hex(),
                'expression':expression.decode('cp1251','backslashreplace'),
                'comparison_count':3,
                'source_indices':list(range(first_first,join+1)),
                'shortcut_indices':[first_jump,second_jump],
                'call_sites':[{'first':first,'last':last,'index':last}
                              for first,last in calls],
                'term_slots':[],
                'rendered_term':expression.decode('cp1251','backslashreplace'),
                'fallthrough':join+1,'branch_target':final['op2']['word0'],
                'conditional_opcode':'JMPZ','effectful_call_chain':True}
    def assigned_loop_and(join:int, evidence:dict) -> dict:
        """Prove one assigned call and one comparison in a loop header."""
        start=join-8
        kinds=['INIT_FCALL_BY_NAME','FETCH_FUNC_ARG','SEND_VAR',
               'DO_FCALL_BY_NAME','ASSIGN','JMPZ_EX',
               'IS_NOT_EQUAL','BOOL','JMPZ']
        if start<0 or [name(i) for i in range(start,join+1)]!=kinds:
            raise Unsupported('Different assigned loop condition')
        for i in range(start,join+1):
            op=ops[i];key=f'{i%8}:{op["encoded_opcode"]}'
            observed=evidence.get(key)
            if (observed is None or observed.get('status')!='confirmed' or
                    observed.get('opcode')!=op.get('decoded_opcode') or
                    mapping['opcodes'].get(key)!=op.get('decoded_opcode')):
                raise Unsupported('Assigned loop lacks confirmed opcode')
        init,fetch,send,call,assign,shortcut,compare,wrapper,final=(
            ops[i] for i in range(start,join+1))
        if (init['op2']['type']!=1 or fetch['op1']['type']!=1 or
                send['op1']!=fetch['result'] or
                call['op1']!=init['op2'] or
                call['result']['type']!=4 or
                assign['op1']['type']!=16 or
                assign['op2']!=call['result'] or
                assign['result']['type']!=4 or
                shortcut['op1']!=assign['result'] or
                shortcut['result']['type']!=2 or
                shortcut['op2']!={'type':8,'word0':join,'word1':1} or
                compare['op1']['type']!=16 or compare['op2']['type']!=1 or
                compare['op2']['constant']['kind']!='integer' or
                compare['result']['type']!=2 or
                wrapper['op1']!=compare['result'] or
                wrapper['result']!=shortcut['result'] or
                final['op1']!=shortcut['result'] or
                final['op2']['type']!=8 or final['op2']['word1']!=1 or
                final['op2']['word0']<=join or
                any(op['extended_value']!=0 for op in
                    (assign,shortcut,compare,wrapper,final))):
            raise Unsupported('Assigned loop slots or targets disagree')
        group={'opcodes':[dict(op,decoded_opcode=choose_opcode(op,mapping))
                          for op in ops],'compiled_vars':[],'loop_records':[]}
        cfg=cfg_for_group('<assigned loop>',group)
        by_first={b['first']:b for b in cfg['basic_blocks']}
        lead=by_first.get(start);middle=by_first.get(start+6)
        tail=by_first.get(join);body=by_first.get(join+1)
        after=by_first.get(final['op2']['word0'])
        if (not all((lead,middle,tail,body,after)) or
                not all(b['reachable'] for b in (lead,middle,tail,body)) or
                lead['last']!=start+5 or middle['last']!=join-1 or
                tail['last']!=join or body['last']!=final['op2']['word0']-1 or
                name(body['last'])!='JMP' or
                ops[body['last']]['op1']!=
                    {'type':8,'word0':start,'word1':1} or
                len(lead['predecessors'])!=2 or
                body['id'] not in lead['predecessors'] or
                middle['predecessors']!=[lead['id']] or
                set(tail['predecessors'])!={lead['id'],middle['id']} or
                body['predecessors']!=[tail['id']] or
                {(e['kind'],e['block']) for e in lead['successors']}!=
                    {('zero',tail['id']),('nonzero',middle['id'])} or
                [(e['kind'],e['block']) for e in middle['successors']]!=
                    [('fallthrough',tail['id'])] or
                {(e['kind'],e['block']) for e in tail['successors']}!=
                    {('zero',after['id']),('nonzero',body['id'])} or
                [(e['kind'],e['block']) for e in body['successors']]!=
                    [('always',lead['id'])] or
                not any(e['from']==body['id'] and e['to']==lead['id']
                        for e in cfg['back_edges'])):
            raise Unsupported('Assigned loop CFG differs')
        analysis=read_definitions(group,title='<assigned loop>')
        if analysis['status']!='analyzed_syntactically':
            raise Unsupported('Assigned loop lacks reaching definitions')
        expected={(start+2,'op1'):{start+1},
                  (start+4,'op2'):{start+3},
                  (start+5,'op1'):{start+4},
                  (start+7,'op1'):{start+6},
                  (join,'op1'):{start+5,start+7}}
        producers={start+1,start+3,start+4,start+5,start+6,start+7}
        uses=[u for u in analysis['temporary_uses']
              if set(u['reaching_definition_indices']) & producers]
        if (len(uses)!=len(expected) or
                {(u['instruction_index'],u['operand']):
                 set(u['reaching_definition_indices']) for u in uses}!=expected):
            raise Unsupported('Assigned loop has external TMP consumers')
        assignment=render_range(ops,cv,mapping,start,start+4,
                                slot(assign['result']))
        right=render_range(ops,cv,mapping,start+6,start+7,
                           slot(wrapper['result']))
        expression=b'('+assignment+b' && '+right+b')'
        return {'join_index':join,'slot':list(slot(final['op1'])),
                'mode':'AND','expression_hex':expression.hex(),
                'expression':expression.decode('cp1251','backslashreplace'),
                'comparison_count':2,
                'source_indices':list(range(start,join+1)),
                'shortcut_indices':[start+5],
                'call_sites':[{'first':start,'last':start+3,'index':start+3}],
                'term_slots':[],
                'rendered_term':expression.decode('cp1251','backslashreplace'),
                'fallthrough':join+1,'branch_target':final['op2']['word0'],
                'conditional_opcode':'JMPZ','loop_assignment_join':True,
                'assignment_index':start+4,
                'assignment_expression':assignment.decode('cp1251','backslashreplace')}
    def term_ending_at(index:int, expected):
        """Prove a pure comparison, optionally preceded by single-dimension
        FETCH_DIM_R operands. Require strict adjacency and matching TEMP slots.
        A comparison operand may also be the result of a call; the call is
        then decoded as one closed segment and inlined into the term.
        """
        consumed=[]
        calls=[]
        slots=[]          # (slot, value) of every slot the term passes through
        peel=[]           # wrappers of the term, outermost first
        # A condition may be wrapped in a boolean conversion and in a negation.
        while index>=0:
            wrapper=ops[index]
            if name(index)=='BOOL' and slot(wrapper['result'])==expected:
                peel.append((slot(wrapper['result']),False))
                expected=slot(wrapper['op1'])
                consumed.append(index)
                index-=1
                continue
            if name(index)=='BOOL_NOT' and slot(wrapper['result'])==expected:
                peel.append((slot(wrapper['result']),True))
                expected=slot(wrapper['op1'])
                consumed.append(index)
                index-=1
                continue
            break
        if index<0:
            raise Unsupported('Condition has no comparison')
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
        # Every wrapper copies the value of the comparison into its own slot;
        # a boolean conversion keeps the value and a negation inverts it.
        # The slots are recorded in the order the decoder produces them, so
        # a block that contains the join can be decoded with the same values.
        base=expression
        slots.append((slot(op['result']),base))
        rendered=base
        for wrapper_slot,is_not in reversed(peel):
            rendered=(b'(!'+rendered+b')' if is_not
                      else b'((bool) '+rendered+b')')
            slots.append((wrapper_slot,rendered))
        # A boolean conversion is the identity in a condition and each
        # negation inverts the term, so only the parity matters.
        negations=sum(1 for _wrapper_slot,is_not in peel if is_not)
        expression=b'!'*(negations%2)+base
        return expression,cursor,consumed,calls,slots,rendered

    found={}
    for join in range(2,len(ops)-1):
        if name(join)=='JMPZ':
            try:
                found[join]=prove_cv_or_join(ops,cv,mapping,join)
            except (Unsupported, IndexError, KeyError, TypeError, ValueError):
                pass
    for join in range(len(ops)):
        if join in found:continue
        final=ops[join]
        if name(join) not in ('JMPZ','JMPNZ','JMPZ_EX','JMPNZ_EX') or final['op1']['type'] not in (2,4):
            continue
        result=slot(final['op1'])
        try:
            last,cursor,included,calls,term_slots,rendered=term_ending_at(join-1,result)
            terms=[last];proof_indices=included[:];shortcuts=[];mode=None
            call_sites=list(calls)
            while cursor>=0 and name(cursor) in ('JMPNZ_EX','JMPZ_EX'):
                jump=ops[cursor];shortcut_kind=name(cursor)
                if jump['op2']['type']!=8 or jump['op2']['word1']!=1:
                    break
                target=jump['op2']['word0']
                # The shortcut has to reach the join without a branch in
                # between: the target may be the instruction in front of the
                # join, the compiler may place the jump there.
                if not (0<=target<=join):
                    break
                if any(name(i) in ('JMP','JMPZ','JMPNZ','JMPZNZ','JMPZ_EX','JMPNZ_EX')
                       for i in range(target,join)):
                    break
                shortcut_slot=slot(jump['op1'])
                if shortcut_slot is None:
                    break
                if mode is not None and shortcut_kind!=mode:
                    break
                mode=shortcut_kind
                expr,cursor2,used,more_calls,_slots,_rendered=term_ending_at(cursor-1,shortcut_slot)
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
                         'term_slots':[{'slot':list(slot),'value_hex':value.hex()}
                                       for slot,value in term_slots],
                         'rendered_term':rendered.decode('cp1251','backslashreplace'),
                         'fallthrough':join+1,
                         'branch_target':final['op2']['word0'],
                         'conditional_opcode':name(join)}
        except (Unsupported, IndexError, KeyError, TypeError):
            continue
    # Keep the effectful two-level reads in their original conditional order.
    # The general comparison proof deliberately rejects this operand shape.
    evidence=None
    for join in range(8,len(ops)):
        if join in found or name(join)!='JMPZ' or name(join-8)!='FETCH_DIM_R':
            continue
        try:
            if evidence is None:evidence=_validated_evidence(OPCODE_MAP)
            found[join]=nested_dimension_join(join,evidence)
        except (Unsupported, ValueError, IndexError, KeyError, TypeError):
            continue
    for join in range(9,len(ops)):
        if join in found or name(join)!='JMPZ' or name(join-1)!='BOOL':
            continue
        try:
            if evidence is None:evidence=_validated_evidence(OPCODE_MAP)
            found[join]=three_call_and(join,evidence)
        except (Unsupported, ValueError, IndexError, KeyError, TypeError):
            continue
    for join in range(8,len(ops)):
        if join in found or name(join)!='JMPZ' or name(join-8)!='INIT_FCALL_BY_NAME':
            continue
        try:
            if evidence is None:evidence=_validated_evidence(OPCODE_MAP)
            found[join]=assigned_loop_and(join,evidence)
        except (Unsupported, ValueError, IndexError, KeyError, TypeError):
            continue
    # A bounded nested form has two OR terms separated by one AND term.
    # The outer JMPZ_EX instructions skip the entire remaining condition;
    # folding either OR alone would leave edges into removed CFG blocks.
    # Keep this proof to CV/constant comparisons and BOOL wrappers, with no
    # calls, fetches or assignments in the folded interval.
    for join,right in list(found.items()):
        try:
            if (name(join)!='JMPZ' or right['mode']!='OR' or
                    right['comparison_count']!=2 or right['call_sites']):
                continue
            right_indices=right['source_indices']
            right_start=right_indices[0]
            if (right_start<1 or
                    right_indices!=list(range(right_start,join+1)) or
                    len(right['shortcut_indices'])!=1 or
                    name(join-1)!='BOOL'):
                continue
            right_shortcut=right['shortcut_indices'][0]
            if (name(right_shortcut)!='JMPNZ_EX' or
                    slot(ops[right_shortcut]['result'])!=slot(ops[join-1]['op1']) or
                    ops[right_shortcut]['op2']['type']!=8 or
                    ops[right_shortcut]['op2']['word1']!=1 or
                    ops[right_shortcut]['op2']['word0']!=join-1):
                continue
            middle_jump=right_start-1
            if name(middle_jump)!='JMPZ_EX':continue
            jump=ops[middle_jump]
            if (jump['op2']['type']!=8 or jump['op2']['word1']!=1 or
                    jump['op2']['word0']!=join):
                continue
            middle,cursor,used,calls,_slots,_rendered=term_ending_at(
                middle_jump-1,slot(jump['op1']))
            if calls or sorted(used)!=list(range(cursor+1,middle_jump)):
                continue
            left=found.get(cursor)
            if (left is None or left['mode']!='OR' or left['comparison_count']!=2 or
                    left['call_sites'] or name(cursor)!='JMPZ_EX'):
                continue
            left_indices=left['source_indices']
            if (left_indices!=list(range(left_indices[0],cursor+1)) or
                    len(left['shortcut_indices'])!=1):
                continue
            left_jump=ops[cursor]
            left_shortcut=ops[left['shortcut_indices'][0]]
            final_slot=slot(ops[join]['op1'])
            if (left_shortcut['op2']['type']!=8 or
                    left_shortcut['op2']['word1']!=1 or
                    left_shortcut['op2']['word0']!=cursor or
                    left_jump['op2']['type']!=8 or left_jump['op2']['word1']!=1 or
                    left_jump['op2']['word0']!=join or
                    slot(left_jump['op1'])!=final_slot or
                    slot(left_jump['result'])!=final_slot or
                    slot(jump['op1'])!=final_slot or
                    slot(jump['result'])!=final_slot or
                    tuple(left['slot'])!=final_slot or
                    tuple(right['slot'])!=final_slot):
                continue
            interval=list(range(left_indices[0],join+1))
            if sorted(set(left_indices+used+[middle_jump]+right_indices))!=interval:
                continue
            allowed=set(COMPARISONS)|{'BOOL','JMPNZ_EX','JMPZ_EX','JMPZ'}
            if any(name(i) not in allowed for i in interval):continue
            if any(ops[i][operand]['type'] not in (1,16)
                   for i in interval if name(i) in COMPARISONS
                   for operand in ('op1','op2')):
                continue
            left_expression=bytes.fromhex(left['expression_hex'])
            right_expression=bytes.fromhex(right['expression_hex'])
            expression=b'('+left_expression+b' && '+middle+b' && '+right_expression+b')'
            found[join]={**right,
                         'mode':'AND','expression_hex':expression.hex(),
                         'expression':expression.decode('cp1251','backslashreplace'),
                         'comparison_count':left['comparison_count']+1+right['comparison_count'],
                         'source_indices':interval,
                         'shortcut_indices':sorted(left['shortcut_indices']+
                                                   [cursor,middle_jump]+
                                                   right['shortcut_indices']),
                         'call_sites':[],'term_slots':[],
                         'rendered_term':expression.decode('cp1251','backslashreplace'),
                         'block_seeds':[
                             {'instruction_index':cursor,'slot':left['slot'],
                              'value_hex':left['expression_hex']},
                             {'instruction_index':join-1,
                              'slot':list(slot(ops[join-1]['op1'])),
                              'value_hex':right['expression_hex']}],
                         'nested':True}
            del found[cursor]
        except (Unsupported, IndexError, KeyError, TypeError, ValueError):
            continue
    # Two complete AND diamonds may be joined by one OR shortcut. Keep both
    # copies of any reads: reducing (A && B) || (A && C) to A && (B || C)
    # would change the number and timing of A's reads.
    for join,right in list(found.items()):
        try:
            if (name(join)!='JMPZ' or right['mode']!='AND' or
                    right['comparison_count']!=2 or right['call_sites'] or
                    not right['source_indices'] or
                    right['source_indices']!=list(range(right['source_indices'][0],join+1))):
                continue
            outer=right['source_indices'][0]-1
            left=found.get(outer)
            if (left is None or name(outer)!='JMPNZ_EX' or
                    left['mode']!='AND' or left['comparison_count']!=2 or
                    left['call_sites'] or
                    left['source_indices']!=list(range(left['source_indices'][0],outer+1)) or
                    ops[outer]['op2']!={'type':8,'word0':join,'word1':1} or
                    ops[outer]['op1']!=ops[join]['op1'] or
                    ops[outer]['result']!=ops[join]['op1'] or
                    name(join-1)!='BOOL' or
                    ops[join-1]['result']!=ops[join]['op1']):
                continue
            first=left['source_indices'][0]
            middle=right['source_indices'][0]
            group={'opcodes':[dict(op,decoded_opcode=choose_opcode(op,mapping))
                              for op in ops], 'compiled_vars':[], 'loop_records':[]}
            cfg=cfg_for_group('<AND OR join>',group)
            by_first={b['first']:b for b in cfg['basic_blocks']}
            lead=by_first.get(first);left_middle=by_first.get(left['shortcut_indices'][0]+1)
            outer_block=by_first.get(outer);right_lead=by_first.get(middle)
            right_middle=by_first.get(right['shortcut_indices'][0]+1)
            right_wrapper=by_first.get(join-1);tail=by_first.get(join)
            if (not all((lead,left_middle,outer_block,right_lead,
                         right_middle,right_wrapper,tail)) or
                    not all(b['reachable'] for b in (lead,left_middle,outer_block,
                                                    right_lead,right_middle,right_wrapper,tail)) or
                    lead['last']!=left['shortcut_indices'][0] or
                    left_middle['last']!=outer-1 or outer_block['last']!=outer or
                    right_lead['last']!=right['shortcut_indices'][0] or
                    right_middle['last']!=join-2 or right_wrapper['last']!=join-1 or
                    tail['last']!=join or
                    left_middle['predecessors']!=[lead['id']] or
                    set(outer_block['predecessors'])!={lead['id'],left_middle['id']} or
                    right_lead['predecessors']!=[outer_block['id']] or
                    right_middle['predecessors']!=[right_lead['id']] or
                    set(right_wrapper['predecessors'])!={right_lead['id'],right_middle['id']} or
                    set(tail['predecessors'])!={outer_block['id'],right_wrapper['id']} or
                    {(e['kind'],e['block']) for e in lead['successors']}!=
                        {('zero',outer_block['id']),('nonzero',left_middle['id'])} or
                    {(e['kind'],e['block']) for e in right_lead['successors']}!=
                        {('zero',right_wrapper['id']),('nonzero',right_middle['id'])} or
                    {(e['kind'],e['block']) for e in outer_block['successors']}!=
                        {('nonzero',tail['id']),('zero',right_lead['id'])}):
                continue
            expression=(b'('+bytes.fromhex(left['expression_hex'])+b' || '+
                        bytes.fromhex(right['expression_hex'])+b')')
            found[join]={**right,'mode':'OR','expression_hex':expression.hex(),
                         'expression':expression.decode('cp1251','backslashreplace'),
                         'comparison_count':4,
                         'source_indices':list(range(first,join+1)),
                         'shortcut_indices':sorted(left['shortcut_indices']+
                                                   [outer]+right['shortcut_indices']),
                         'term_slots':[],
                         'rendered_term':expression.decode('cp1251','backslashreplace'),
                         'block_seeds':[
                             {'instruction_index':outer,'slot':left['slot'],
                              'value_hex':left['expression_hex']},
                             {'instruction_index':join-1,
                              'slot':list(spot(ops[join-1]['op1'])),
                              'value_hex':right['expression_hex']}],
                         'nested':True}
            del found[outer]
        except (Unsupported, IndexError, KeyError, TypeError, ValueError):
            continue
    # The bounded layouts below need a whole-interval truth-table proof.
    # Discard narrower overlapping proofs only after the wider proof succeeds.
    from .bounded_and import bounded_and_proofs
    if evidence is None:
        evidence = _validated_evidence(OPCODE_MAP)
    for join, proof in bounded_and_proofs(ops, cv, mapping, evidence).items():
        interval = set(proof['source_indices'])
        for old in list(found):
            if interval.intersection(found[old]['source_indices']):
                del found[old]
        found[join] = proof
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
