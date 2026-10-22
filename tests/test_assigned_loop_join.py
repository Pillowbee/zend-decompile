"""Synthetic CFG tests; these do not establish the Zend Encoder format."""
from __future__ import annotations

import json
import unittest

from zend_decompiler.assets import OPCODE_MAP
from zend_decompiler.crossblock import join_proofs
from zend_decompiler.readonly_dataflow import _validated_evidence
from zend_decompiler.restore_core import build_group
from zend_decompiler.structure import StructureError, build_graph


def node(kind, value=0, other=0):
    return {'type':kind,'word0':value,'word1':other}


def string(value):
    return {'type':1,'constant':{'kind':'string','raw_hex':value.encode().hex()}}


def integer(value):
    return {'type':1,'constant':{'kind':'integer','value':value}}


def op(index, encoded, native, result=None, op1=None, op2=None, extended=0):
    return {'index':index,'encoded_opcode':encoded,'decoded_opcode':native,
            'result':result if result is not None else node(8),
            'op1':op1 if op1 is not None else node(8),
            'op2':op2 if op2 is not None else node(8),
            'extended_value':extended,'line':index+1}


def fixture():
    mapping=json.loads(OPCODE_MAP.read_text(encoding='utf-8'))
    evidence=_validated_evidence(OPCODE_MAP)
    native=[59,92,66,61,38,46,18,52,43]
    encoded=[]
    for index,number in enumerate(native,3):
        keys=[key for key,value in mapping['opcodes'].items()
              if key.startswith(f'{index%8}:') and value==number and
              evidence.get(key,{}).get('status')=='confirmed']
        assert keys,(index,number)
        encoded.append(int(keys[0].split(':')[1]))
    name=string('check')
    ops=[op(i,250+i,53,node(2,9+i)) for i in range(3)]
    for i in range(3):mapping['opcodes'][f'{i}:{250+i}']=53
    ops.extend((
        op(3,encoded[0],59,op2=name),
        op(4,encoded[1],92,node(4,0),string('arg'),node(8,1,1),extended=1),
        op(5,encoded[2],66,op1=node(4,0),op2=node(8,1,1),extended=61),
        op(6,encoded[3],61,node(4,1),name,node(8,0,1),extended=1),
        op(7,encoded[4],38,node(4,2),node(16,0),node(4,1)),
        op(8,encoded[5],46,node(2,0),node(4,2),node(8,11,1)),
        op(9,encoded[6],18,node(2,1),node(16,1),integer(0)),
        op(10,encoded[7],52,node(2,0),node(2,1)),
        op(11,encoded[8],43,op1=node(2,0),op2=node(8,13,1)),
        op(12,253,42,op1=node(8,3,1)),
        op(13,254,62,op1=integer(0)),
    ))
    mapping['opcodes']['4:253']=42
    mapping['opcodes']['5:254']=62
    group={'opcodes':ops,'compiled_vars':[
        {'index':0,'name_hex':b'value'.hex()},
        {'index':1,'name_hex':b'limit'.hex()}],
        'loop_records':[]}
    return group,mapping


class AssignedLoopJoinTests(unittest.TestCase):
    def proof(self, group, mapping):
        cv={v['index']:bytes.fromhex(v['name_hex']) for v in group['compiled_vars']}
        return join_proofs(group['opcodes'],cv,mapping).get(11)

    def test_assignment_is_emitted_once_in_loop_condition(self):
        group,mapping=fixture()
        proof=self.proof(group,mapping)
        self.assertTrue(proof['loop_assignment_join'])
        body,audit=build_group(group,mapping,'<main>')
        text='\n'.join(body)
        self.assertEqual(text.count('$value = check($arg)'),1)
        self.assertIn('while (',text)
        self.assertEqual(len(audit['folded_short_circuits']),1)
        self.assertTrue(audit['loops'])

    def test_wrong_shortcut_target_is_rejected(self):
        group,mapping=fixture()
        group['opcodes'][8]['op2']=node(8,10,1)
        self.assertIsNone(self.proof(group,mapping))

    def test_wrong_assignment_slot_is_rejected(self):
        group,mapping=fixture()
        group['opcodes'][7]['result']=node(4,8)
        self.assertIsNone(self.proof(group,mapping))

    def test_extra_consumer_of_temporary_is_rejected(self):
        group,mapping=fixture()
        group['opcodes'][12]=op(12,253,42,op1=node(8,3,1),op2=node(2,0))
        self.assertIsNone(self.proof(group,mapping))

    def test_changed_back_edge_is_rejected(self):
        group,mapping=fixture()
        group['opcodes'][12]['op1']=node(8,13,1)
        self.assertIsNone(self.proof(group,mapping))

    def test_extra_entry_into_join_is_rejected(self):
        group,mapping=fixture()
        group['opcodes'][2]=op(2,252,43,op1=node(16,1),
                               op2=node(8,11,1))
        mapping['opcodes']['2:252']=43
        self.assertIsNone(self.proof(group,mapping))

    def test_extra_header_statement_cannot_be_transferred(self):
        group,mapping=fixture()
        proof=self.proof(group,mapping)
        assignment=proof['assignment_expression']
        data={'source':'synthetic','total':14,'proven_short_circuit_joins':[proof],
              'blocks':[
                  {'id':'B000','first':0,'last':2,'statements':[],
                   'statement_sources':[],'branch':None,
                   'successors':[{'block':'B003','kind':'fallthrough','target_instruction':3}]},
                  {'id':'B003','first':3,'last':8,
                   'statements':[assignment[1:-1]+';','echo 1;'],
                   'statement_sources':[7,8],
                   'branch':{'opcode':'JMPZ_EX','condition':assignment,'target':11},
                   'successors':[{'block':'B011','kind':'zero','target_instruction':11},
                                 {'block':'B009','kind':'nonzero','target_instruction':9}]},
                  {'id':'B009','first':9,'last':10,'statements':[],
                   'statement_sources':[],'branch':None,
                   'successors':[{'block':'B011','kind':'fallthrough','target_instruction':11}]},
                  {'id':'B011','first':11,'last':11,'statements':[],
                   'statement_sources':[],
                   'branch':{'opcode':'JMPZ','condition':proof['expression'],'target':13},
                   'successors':[{'block':'B013','kind':'zero','target_instruction':13},
                                 {'block':'B012','kind':'nonzero','target_instruction':12}]},
                  {'id':'B012','first':12,'last':12,'statements':[],
                   'statement_sources':[],
                   'branch':{'opcode':'JMP','condition':'','target':3},
                   'successors':[{'block':'B003','kind':'always','target_instruction':3}]},
                  {'id':'B013','first':13,'last':13,'statements':['return 0;'],
                   'statement_sources':[13],'branch':None,'successors':[]}]}
        with self.assertRaisesRegex(StructureError,'exactly once'):
            build_graph(data)


if __name__=='__main__':
    unittest.main()
