#!/usr/bin/env python3
"""Offline, fail-closed restoration of a validated get_wares.php control-flow prefix.

Research tool, *not* a replacement for get_wares.php. Neither PHP nor ZendOptimizer
is invoked. Recover the first 78 instructions and the final 5 instructions while
preserving source-level caveats. Every emitted construct has a source-index proof.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from .assets import OPCODE_MAP, DICTIONARY
from dataclasses import dataclass
from collections import Counter
from .serial_parser import decompress_encoded, parse_binary
from .calibrate import choose_opcode
from .call_protocol import CallProtocolError, DirectCallBuffer
from . import encoder_calls

IDENT = re.compile(rb'^[A-Za-z_][A-Za-z_0-9]*$')

# Sentinel for the element of a foreach.  The element has no PHP expression
# outside the foreach construct, so the value is marked instead of guessed.
# Any statement that would leak the sentinel is refused.
FOREACH_VALUE = b'__ZEND_FOREACH_VALUE__'

class Unsupported(Exception):
    pass


def php_string(raw: bytes) -> bytes:
    """Losslessly quote PHP byte string using literal single quotes."""
    return b"'" + raw.replace(b'\\', b'\\\\').replace(b"'", b"\\'") + b"'"


def sym(raw: bytes) -> bytes:
    if not IDENT.fullmatch(raw):
        raise Unsupported('Non-simple PHP identifier: '+repr(raw))
    return raw


def const(node):
    if node['type'] != 1:
        raise Unsupported('Expected constant')
    v=node['constant']
    if v['kind']=='string': return php_string(bytes.fromhex(v['raw_hex']))
    if v['kind']=='integer': return str(v['value']).encode('ascii')
    if v['kind']=='null': return b'NULL'
    raise Unsupported('Unsupported literal: '+repr(v))


def raw_string(node):
    if node['type']!=1 or node['constant']['kind']!='string':
        raise Unsupported('Expected literal string')
    return bytes.fromhex(node['constant']['raw_hex'])


def spot(node):
    if node['type'] not in (2,4): raise Unsupported('Expected TMP/VAR slot')
    return node['type'],node['word0'],node['word1']


def _foreach_facts(before: dict, after: dict) -> dict:
    """Facts of a foreach that this block contributed.

    The array of the foreach is known where FE_RESET is decoded, the bound
    variable where the assignment is decoded; the header block is the one
    where the fetch is decoded.  The facts are merged later by their id.
    """
    facts = {}
    if after.get('stage') == 'fetch' and before.get('stage') == 'reset':
        facts['id'] = after.get('id')
        facts['array'] = after['array'].decode('cp1251')
    if after.get('stage') == 'bound' and before.get('stage') in ('fetch', 'binding'):
        facts['id'] = after.get('id')
        facts['variable'] = after['variable'].decode('cp1251')
        facts['by_ref'] = bool(after.get('by_ref'))
    return facts


def _merge_foreach_facts(blocks: list) -> None:
    """Give every foreach header the array and the bound variable."""
    arrays = {}
    variables = {}
    for block in blocks:
        facts = block.get('foreach') or {}
        if 'array' in facts:
            arrays[facts['id']] = facts
        if 'variable' in facts:
            variables[facts['id']] = facts
    for block in blocks:
        facts = block.get('foreach') or {}
        if 'id' not in facts:
            continue
        merged = dict(facts)
        merged.update(arrays.get(facts['id'], {}))
        merged.update(variables.get(facts['id'], {}))
        block['foreach'] = merged


@dataclass
class Segment:
    statements: list[bytes]
    branch: tuple[str,bytes,int] | None
    covered: list[int]
    last_assignment: tuple[bytes,bytes] | None = None
    fired_rules: dict[str,int] | None = None
    encoder_calls: list | None = None
    statement_sources: list[int] | None = None


class Decoder:
    def __init__(self,ops,cv,mapping,symbols=None,callees=None,context=None):
        self.ops=ops
        self.cv=cv
        self.map=mapping
        # Encoder-level call support: the file symbol table and the functions
        # declared in the same file.  Both stay empty when a file carries no
        # encoder call sites, which keeps the decoder fail-closed.
        self.symbols=list(symbols or [])
        self.callees=dict(callees or {})
        # State that spans the basic blocks of one group (foreach construct).
        self.context=context if context is not None else {}
        self.defs={}
        self.call_stack=[]
        self.direct_call_args=DirectCallBuffer()
        self.lines=[]
        self.branch=None
        self.covered=[]
        self.last_assignment=None
        self.pending_calls={}
        self.consumed_call_slots=set()
        self.array_items={}
        self.silence_slot=None
        self.silenced_calls=0
        self.fired_rules=Counter()
        self.current_index=None
        self.encoder_calls=[]
        # Instruction index that produced every emitted statement.
        self.line_sources=[]

    def kind(self,op):
        # Encoder call terminators are recognised on the Encoder level.  Their
        # native opcode number is unresolved, so the native name is never used.
        if encoder_calls.is_call_terminator(op):
            return 'ENCODER_CALL'
        k=choose_opcode(op,self.map)
        if k is None: raise Unsupported('Unknown opcode #'+str(op['index']))
        # In the saved PHP 5.2-family header, native opcode 4 is ZEND_DIV.
        # This names the *native* operation only; the Encoder key remains inferred.
        return self.map['names'].get(str(k), {4:'DIV'}.get(k,str(k)))

    def val(self,node):
        t=node['type']
        if t==1:return const(node)
        if t==16:
            name=self.cv.get(node['word0'])
            if name is None:raise Unsupported('CV not in table')
            return b'$'+sym(name)
        if t in (2,4):
            k=spot(node)
            if k not in self.defs:raise Unsupported('Unresolved temporary '+str(k))
            if k in self.pending_calls:
                self.lines[self.pending_calls.pop(k)]=None
                self.consumed_call_slots.add(k)
            elif k in self.consumed_call_slots:
                raise Unsupported('Multiple reads of inlined function-call temporary '+str(k))
            expr=self.defs[k]
            return (b' . '.join(expr) if expr else b"''") if isinstance(expr,list) else expr
        raise Unsupported('Unexpected UNUSED operand')

    def dest(self,node):
        if node['type']!=8 or node['word1']!=1:
            raise Unsupported('Unexpected branch operand '+repr(node))
        return node['word0']

    def put(self,node,text):
        k=spot(node)
        if k in self.pending_calls:
            # The previous function call was already emitted as a standalone
            # expression statement. Its result can be overwritten safely.
            # Preserve that statement instead of treating slot reuse as loss.
            self.pending_calls.pop(k)
        self.consumed_call_slots.discard(k)
        self.defs[k] = text

    def _is_foreach_binding(self,lhs_node,rhs_node) -> bool:
        """True when an assignment binds the value of the current foreach."""
        state=self.context.get('foreach')
        if not state or state.get('stage') not in ('fetch','binding'):
            return False
        if lhs_node.get('type')!=16:
            return False
        if rhs_node.get('type') not in (2,4):
            return False
        return spot(rhs_node) in (state.get('element_slot'),state.get('binding_slot'))

    def emit_call(self,result_node,expr):
        """Emit a call expression and keep it available as a side effect."""
        if self.silence_slot is not None:
            if self.silenced_calls:
                raise Unsupported('Multiple calls in @ region')
            expr=b'@'+expr
            self.silenced_calls+=1
        self.put(result_node,expr)
        # Preserve an unconsumed call as a side-effect statement. When
        # its return value is consumed, remove this placeholder in-place.
        self.pending_calls[spot(result_node)]=len(self.lines)
        self.lines.append(expr+b';')

    def run(self,start,end):
        """Inclusive indices, segment must end with no unfinished function calls."""
        for idx in range(start,end+1):
            op=self.ops[idx]
            self.current_index=idx
            if op['index']!=idx:raise Unsupported('Index mismatch')
            kind=self.kind(op)
            a,b,r=op['op1'],op['op2'],op['result']
            self.covered.append(idx)
            if kind=='RECV':
                # RECV declares a positional parameter in the function signature;
                # it does not produce a runtime statement in the function body.
                if a['type']!=1 or a['constant']['kind']!='integer' or r['type']!=16:
                    raise Unsupported('Unexpected RECV encoding')
                if a['constant']['value']!=r['word0']+1 or r['word0'] not in self.cv:
                    raise Unsupported('Non-canonical RECV parameter index')
            elif kind=='INIT_STRING':
                self.put(r,[])
            elif kind=='INIT_ARRAY':
                if b['type']!=8:raise Unsupported('Keyed INIT_ARRAY unsupported')
                items=[] if a['type']==8 else [self.val(a)]
                self.array_items[spot(r)]=items
                self.put(r,b'array('+b', '.join(items)+b')')
            elif kind=='ADD_ARRAY_ELEMENT':
                if b['type']!=8:raise Unsupported('Keyed ADD_ARRAY_ELEMENT unsupported')
                key=spot(r)
                if key not in self.array_items:raise Unsupported('Unmatched ADD_ARRAY_ELEMENT')
                self.array_items[key].append(self.val(a))
                self.put(r,b'array('+b', '.join(self.array_items[key])+b')')
            elif kind in ('ADD_STRING','ADD_VAR','ADD_CHAR'):
                pieces=self.defs.get(spot(a))
                if not isinstance(pieces,list):raise Unsupported('String builder provenance lost at '+str(idx))
                if kind=='ADD_CHAR':
                    if b['type']!=1 or b['constant']['kind']!='integer' or not (0<=b['constant']['value']<=255):
                        raise Unsupported('ADD_CHAR not a byte literal')
                    val=php_string(bytes([b['constant']['value']]))
                else:
                    val=const(b) if kind=='ADD_STRING' else self.val(b)
                pieces.append(val)
                self.put(r,pieces)
            elif kind=='FETCH_W':
                if b['type']!=8:raise Unsupported('Complex FETCH_W unsupported')
                if a['type']==1:
                    # A global variable: $GLOBALS['name'].
                    var=sym(raw_string(a))
                    self.put(r,b'$GLOBALS['+php_string(var)+b']')
                elif a['type']==16:
                    # A variable variable: the container of the variable that
                    # is named by the value of the compiled variable.
                    self.put(r,b'$$'+sym(self.cv[a['word0']]))
                else:
                    raise Unsupported('Complex FETCH_W unsupported')
            elif kind=='FETCH_R':
                if b['type']!=8 or b['word0']!=1 or b['word1']!=1:
                    raise Unsupported('Noncanonical dynamic-variable FETCH_R')
                self.put(r,b'${'+self.val(a)+b'}')
            elif kind=='FETCH_CONSTANT':
                if a['type']!=1 or a['constant']['kind']!='string' or b['type']!=8:
                    raise Unsupported('Unsupported FETCH_CONSTANT encoding')
                self.put(r,sym(raw_string(a)))
            elif kind=='ASSIGN_REF':
                lhs=self.val(a);rhs=self.val(b)
                if rhs==b'$GLOBALS['+php_string(lhs[1:])+b']':
                    self.lines.append(b'global '+lhs+b';')
                elif lhs.startswith(b'$') and rhs.startswith(b'$'):
                    # A reference assignment.  The operands are the containers
                    # of the target and of the source.
                    self.lines.append(lhs+b' = &'+rhs+b';')
                else:
                    raise Unsupported('Non-global ASSIGN_REF unsupported')
            elif kind in ('FETCH_DIM_R','FETCH_DIM_FUNC_ARG','FETCH_DIM_W'):
                if b['type']==8:
                    if kind!='FETCH_DIM_W':raise Unsupported('Unreadable append access')
                    suffix=b'[]'
                else:suffix=b'['+self.val(b)+b']'
                self.put(r,self.val(a)+suffix)
            elif kind in ('ADD','SUB','MUL','DIV'):
                operator={ 'ADD': b' + ', 'SUB': b' - ', 'MUL': b' * ', 'DIV': b' / ' }[kind]
                self.put(r,b'('+self.val(a)+operator+self.val(b)+b')')
            elif kind in ('IS_NOT_EQUAL','IS_EQUAL','IS_SMALLER','IS_SMALLER_OR_EQUAL'):
                sign={'IS_NOT_EQUAL':b' != ', 'IS_EQUAL':b' == ','IS_SMALLER':b' < ', 'IS_SMALLER_OR_EQUAL':b' <= '}[kind]
                self.put(r,b'('+self.val(a)+sign+self.val(b)+b')')
            elif kind=='BEGIN_SILENCE':
                if self.silence_slot is not None or a['type']!=8 or b['type']!=8:
                    raise Unsupported('Unsupported or nested silence region at '+str(idx))
                self.silence_slot=spot(r)
                self.silenced_calls=0
            elif kind=='END_SILENCE':
                if self.silence_slot is None or spot(a)!=self.silence_slot or self.silenced_calls!=1:
                    raise Unsupported('Unpaired or complex silence region at '+str(idx))
                self.silence_slot=None
                self.silenced_calls=0
            elif kind=='INIT_FCALL_BY_NAME':
                self.call_stack.append({'name':sym(raw_string(b)), 'args':[]})
            elif kind=='FETCH_FUNC_ARG':
                self.put(r,b'$'+sym(raw_string(a)))
            elif kind in ('SEND_VAR','SEND_VAL','SEND_VAR_NO_REF'):
                argument=self.val(a)
                if self.call_stack:
                    self.call_stack[-1]['args'].append(argument)
                else:
                    if b['type']!=8 or b['word1']!=1:
                        raise Unsupported('Unsupported direct-call SEND operand')
                    try:
                        self.direct_call_args.push(b['word0'],argument)
                    except CallProtocolError as exc:
                        raise Unsupported(str(exc)) from exc
            elif kind in ('DO_FCALL','DO_FCALL_BY_NAME'):
                if kind=='DO_FCALL':
                    # PHP 5.2 can emit SEND_* / DO_FCALL with no INIT opcode.
                    # Own-source compile-only native trace: corpus/compile_only_dumps/01_calls.log.
                    if self.call_stack:
                        raise Unsupported('Direct DO_FCALL inside initialized call state')
                    if b['type']!=8 or b['word0']!=0 or b['word1']!=1:
                        raise Unsupported('Unsupported direct DO_FCALL operand2')
                    name=sym(raw_string(a))
                    try:
                        args=self.direct_call_args.finish(op['extended_value'])
                    except CallProtocolError as exc:
                        raise Unsupported(str(exc)) from exc
                else:
                    if not self.call_stack:
                        raise Unsupported('DO without initialized call')
                    call=self.call_stack.pop()
                    name=sym(raw_string(a))
                    if call['name'] != name:
                        raise Unsupported('Function-name mismatch')
                    args=call['args']
                expr=name+b'('+b', '.join(args)+b')'
                self.emit_call(r,expr)
            elif kind=='ENCODER_CALL':
                # Encoder-level call: the callee is named by an index into the
                # file symbol table, the argument count is the encoded
                # extended_value.  Resolved fail-closed; nothing is guessed.
                if self.call_stack:
                    raise Unsupported('Encoder call inside an initialized call state')
                try:
                    site=encoder_calls.resolve(op,self.ops,self.map,self.symbols,self.callees)
                except encoder_calls.CallSiteError as exc:
                    raise Unsupported('Encoder call rejected: '+str(exc)) from exc
                try:
                    args=self.direct_call_args.finish(site['argc'])
                except CallProtocolError as exc:
                    raise Unsupported(str(exc)) from exc
                expr=site['name']+b'('+b', '.join(args)+b')'
                self.encoder_calls.append({'index':op['index'],
                    'callee':site['name'].decode('ascii'),
                    'argc':site['argc'],
                    'symbol_index':site['symbol_index'],
                    'send_indices':site['send_indices']})
                self.emit_call(r,expr)
            elif kind=='ASSIGN':
                if self._is_foreach_binding(a,b):
                    # The binding of the loop variable; the foreach construct
                    # carries it, so no separate statement is emitted.
                    lhs=self.val(a)
                    self.val(b)
                    state=self.context['foreach']
                    state['variable']=lhs
                    state['stage']='bound'
                    self.put(r,FOREACH_VALUE)
                else:
                    lhs=self.val(a); rhs=self.val(b)
                    if isinstance(rhs,list):rhs=b' . '.join(rhs) if rhs else b"''"
                    stmt=lhs+b' = '+rhs
                    self.lines.append(stmt+b';')
                    self.put(r,b'('+stmt+b')')
                    self.last_assignment=(stmt,spot(r))
            elif kind=='ASSIGN_CONCAT':
                lhs=self.val(a);rhs=self.val(b)
                stmt=lhs+b' .= '+rhs
                self.lines.append(stmt+b';')
                self.put(r,b'('+stmt+b')')
            elif kind=='PRINT':
                self.lines.append(b'print '+self.val(a)+b';')
                self.put(r,b'1')
            elif kind=='FREE':
                state=self.context.get('foreach')
                if state and spot(a)==state.get('element_slot'):
                    # The freed value is the foreach element; it has no value
                    # outside the construct and produces no statement.
                    pass
                else:
                    self.val(a)
            elif kind=='SWITCH_FREE':
                # Releases a foreach iterator or a switch temporary.  It
                # produces no statement and no value, so the operand is only
                # checked for its shape and never resolved.
                if a['type'] not in (2,4):
                    raise Unsupported('Unexpected SWITCH_FREE operand')
            elif kind=='FE_RESET':
                # foreach: the array that is iterated.
                expr=self.val(a)
                self.put(r,expr)
                counter=self.context.get('foreach_counter',0)
                self.context['foreach_counter']=counter+1
                self.context['foreach']={'id':counter,'array':expr,
                                         'iterator_slot':spot(r),'stage':'reset'}
            elif kind=='FE_FETCH':
                # foreach: fetch the next element.  The element has no PHP
                # expression outside the foreach construct.  The iterator is
                # read from the construct state, because the reset may live in
                # the previous basic block.
                state=self.context.get('foreach')
                if not state or state.get('stage')!='reset':
                    raise Unsupported('foreach fetch without a reset')
                if spot(a)!=state.get('iterator_slot'):
                    raise Unsupported('foreach fetch reads a foreign iterator')
                self.put(r,FOREACH_VALUE)
                state['stage']='fetch'
                state['element_slot']=spot(r)
                if self.branch is not None:raise Unsupported('Multiple branches in segment')
                self.branch=('FE_FETCH',b'',self.dest(b))
            elif kind=='FETCH_DIM_TMP_VAR':
                # foreach by reference: the element is bound as a reference.
                state=self.context.get('foreach')
                if not state or state.get('stage')!='fetch':
                    raise Unsupported('foreach binding outside a foreach fetch')
                if spot(a)!=state.get('element_slot'):
                    raise Unsupported('foreach binding reads a foreign slot')
                if b['type']!=1 or b.get('constant',{}).get('kind')!='integer' or b['constant'].get('value')!=0:
                    raise Unsupported('Unexpected foreach binding dimension')
                self.put(r,FOREACH_VALUE)
                state['stage']='binding'
                state['binding_slot']=spot(r)
                state['by_ref']=True
            elif kind=='ASSIGN' and self._is_foreach_binding(a,b):
                # The binding of the loop variable; the foreach construct
                # carries it, so no separate statement is emitted.
                lhs=self.val(a)
                self.val(b)
                state=self.context['foreach']
                state['variable']=lhs
                state['stage']='bound'
                self.put(r,FOREACH_VALUE)
            elif kind=='PRE_INC':
                rhs=self.val(a)
                self.lines.append(b'++'+rhs+b';')
                self.put(r,b'(++'+rhs+b')')
            elif kind=='BOOL_NOT':
                self.put(r,b'(!'+self.val(a)+b')')
            elif kind=='BOOL':
                self.put(r,b'((bool) '+self.val(a)+b')')
            elif kind=='CONCAT':
                self.put(r,b'('+self.val(a)+b' . '+self.val(b)+b')')
            elif kind in ('JMPNZ_EX','JMPZ_EX'):
                if self.branch is not None:raise Unsupported('Multiple branches in segment')
                cond=self.val(a)
                self.put(r,cond)
                self.branch=(kind,cond,self.dest(b))
            elif kind=='JMPZNZ':
                if self.branch is not None:raise Unsupported('Multiple branches in segment')
                self.branch=(kind,self.val(a),self.dest(b))
            elif kind in ('JMPZ','JMPNZ'):
                if self.branch is not None:raise Unsupported('Multiple branches in segment')
                self.branch=(kind,self.val(a),self.dest(b))
            elif kind=='JMP':
                if self.branch is not None:raise Unsupported('Multiple branches in segment')
                self.branch=(kind,b'',self.dest(a))
            elif kind=='ECHO':
                self.lines.append(b'echo '+self.val(a)+b';')
            elif kind=='INCLUDE_OR_EVAL':
                if b['type']!=8 or b['word1']!=1:
                    raise Unsupported('Unknown include flags')
                form={1:b'eval',2:b'include',4:b'include_once',8:b'require',16:b'require_once'}.get(b['word0'])
                if form is None:raise Unsupported('Unknown include mode')
                self.lines.append(form+b' '+self.val(a)+b';')
            elif kind=='RETURN':
                self.lines.append(b'return '+self.val(a)+b';')
            else:
                raise Unsupported('Unsupported opcode #'+str(idx)+' '+kind)
            # Count actual completed Decoder branches, not mere opcode occurrences.
            self.fired_rules[kind]+=1
            # Every statement emitted by this instruction belongs to it.
            while len(self.line_sources)<len(self.lines):
                self.line_sources.append(idx)
        if self.call_stack:raise Unsupported('Incomplete function calls')
        try:
            self.direct_call_args.require_empty()
        except CallProtocolError as exc:
            raise Unsupported(str(exc)) from exc
        if self.silence_slot is not None:raise Unsupported('Silence region crosses block boundary')
        statements=[line for line in self.lines if line is not None]
        if any(FOREACH_VALUE in line for line in statements):
            # The value of a foreach element only exists inside the foreach
            # construct.  A leaked sentinel means the construct was not
            # recognised, and the block is refused instead of guessed.
            raise Unsupported('Foreach element value used outside the foreach construct')
        sources=[src for line,src in zip(self.lines,self.line_sources) if line is not None]
        return Segment(statements,self.branch,self.covered,self.last_assignment,
                       dict(self.fired_rules),list(self.encoder_calls),sources)


def require_branch(seg,kind,dest):
    if seg.branch is None or seg.branch[0]!=kind or seg.branch[2]!=dest:
        raise Unsupported('Unexpected branch: '+repr(seg.branch))
    return seg.branch[1]


def indent(lines,levels=1):
    return [b'    '*levels + x for x in lines]


def recover(g,m):
    ops=g['opcodes']
    if len(ops)!=488:raise Unsupported('This release expects 488-opcode get_wares.php fixture')
    for op in ops:op['decoded_opcode']=choose_opcode(op,m)
    cv={x['index']:bytes.fromhex(x['name_hex']) for x in g['compiled_vars']}
    def seg(a,b):return Decoder(ops,cv,m).run(a,b)
    # The following edges are checked in the raw binary; no regex parsing of IR.
    a=seg(0,17)
    if a.branch:raise Unsupported('Unexpected branch in initialization')
    b=seg(18,23)
    cond=require_branch(b,'JMPZ',483)
    if len(b.statements)!=1 or b.last_assignment is None or not cond.startswith(b'('):
        raise Unsupported('Cannot safely lift loop condition')
    if b.statements[0][:-1] != cond[1:-1]:
        raise Unsupported('Loop assignment and condition differ')
    c=seg(24,47); cmp1=require_branch(c,'JMPZ',53)
    then=seg(48,52);require_branch(then,'JMP',54)
    otherwise=seg(53,53)
    d=seg(54,73);cmp2=require_branch(d,'JMPZ',75)
    set2=seg(74,74)
    e=seg(75,76);cmp3=require_branch(e,'JMPZ',78)
    set3=seg(77,77)
    tailcond=seg(483,484);cmp4=require_branch(tailcond,'JMPZ',486)
    tailinclude=seg(485,485)
    fin=seg(486,487)
    if any([len(tailcond.statements),len(e.statements)]):raise Unsupported('Unexpected condition side effects')
    php=[b'<?php',b'/*',b' * NON-EXECUTING RESEARCH ARTIFACT. This is an incomplete excerpt,',
         b' * NOT a replacement for get_wares.php. The first 78 of 488',
         b' * serialized instructions and the final 5 are represented.',b' */',
         b'if (false) { // guard prevents accidental execution',
         *indent(a.statements), b'    while ('+cond+b') {',
         *indent(c.statements,2), b'        if '+cmp1+b' {',
         *indent(then.statements,3),b'        } else {',
         *indent(otherwise.statements,3),b'        }',
         *indent(d.statements,2),b'        if '+cmp2+b' {',
         *indent(set2.statements,3),b'        }',
         b'        if '+cmp3+b' {',
         *indent(set3.statements,3),b'        }',
         b'        /* INCOMPLETE: original instructions #78..#482 omitted. */',
         b'    }',b'    if '+cmp4+b' {',*indent(tailinclude.statements,2),b'    }',
         *indent(fin.statements),b'}',b'']
    # The tail is a separate CFG region, not consecutive with #77.
    covered=sorted(set(x for group in (a,b,c,then,otherwise,d,set2,e,set3,tailcond,tailinclude,fin)
                       for x in group.covered))
    if covered!=list(range(78))+list(range(483,488)):
        raise Unsupported('Coverage mismatch')
    results={'file':'get_wares.php','source_instructions':len(ops),'covered':covered,
             'covered_count':len(covered),'unrecovered_range':[78,482],
             'branch_checks':{'loop_false':483,'first_if_false':53,'first_if_join':54,
                              'second_if_false':75,'third_if_false':78,'tail_if_false':486},
             'validated_structure':'while + if/else + if + if + tail if',
             'non_executable':True,'full_semantic_equivalence':False}
    return b'\n'.join(php),results


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path)
    p.add_argument('--dictionary',type=Path,default=DICTIONARY)
    p.add_argument('--map',type=Path,default=OPCODE_MAP)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--audit',type=Path)
    args=p.parse_args()
    streams=decompress_encoded(args.input,args.dictionary.read_bytes())
    if len(streams)!=1:raise Unsupported('Expected exactly one matching stream')
    parsed=parse_binary(streams[0][1]);mapping=json.loads(args.map.read_text())
    source,report=recover(parsed['main'],mapping)
    args.out.write_bytes(source)
    if args.audit:args.audit.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(f'Recovered {report["covered_count"]}/{report["source_instructions"]} instruction records (partial, non-executing PHP)')

if __name__=='__main__':main()
