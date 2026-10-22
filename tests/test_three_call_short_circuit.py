"""Synthetic op_array checks; these do not establish the Encoder format."""
from __future__ import annotations

import json
import unittest

from zend_decompiler.assets import OPCODE_MAP
from zend_decompiler.crossblock import join_proofs
from zend_decompiler.readonly_dataflow import _validated_evidence
from zend_decompiler.restore_core import build_group


def operand(kind, value=0, other=0):
    return {'type':kind,'word0':value,'word1':other}


def string(value):
    return {'type':1,'constant':{'kind':'string','raw_hex':value.encode().hex()}}


def integer(value):
    return {'type':1,'constant':{'kind':'integer','value':value}}


def instruction(index, encoded, native, result=None, op1=None, op2=None):
    return {'index':index,'encoded_opcode':encoded,'decoded_opcode':native,
            'result':result if result is not None else operand(8),
            'op1':op1 if op1 is not None else operand(8),
            'op2':op2 if op2 is not None else operand(8),
            'extended_value':0,'line':index+1}


def fixture():
    mapping=json.loads(OPCODE_MAP.read_text(encoding='utf-8'))
    evidence=_validated_evidence(OPCODE_MAP)
    shape=[59,61,13,46,59,61,13,52,46,59,61,52,43]
    encoded=[]
    for index,native in enumerate(shape,1):
        keys=[key for key,value in mapping['opcodes'].items()
              if key.startswith(f'{index%8}:') and value==native and
              evidence.get(key,{}).get('status')=='confirmed']
        assert keys,(index,native)
        encoded.append(int(keys[0].split(':')[1]))
    ops=[instruction(0,255,53,operand(2,9))]
    mapping['opcodes']['0:255']=53
    names=['first','second','third']
    for k,(begin,var) in enumerate(((1,0),(5,1),(10,2))):
        call=string(names[k])
        ops.append(instruction(begin,encoded[begin-1],59,op2=call))
        ops.append(instruction(begin+1,encoded[begin],61,operand(4,var),op1=call))
        if k<2:
            negative=3 if k==0 else 7
            ops.append(instruction(negative,encoded[negative-1],13,
                                   operand(2,k),operand(4,var)))
            if k==1:
                ops.append(instruction(8,encoded[7],52,operand(2,0),operand(2,1)))
            jump=4 if k==0 else 9
            ops.append(instruction(jump,encoded[jump-1],46,operand(2,0),
                                   operand(2,0),operand(8,13,1)))
        else:
            ops.append(instruction(12,encoded[11],52,operand(2,0),operand(4,var)))
    ops.append(instruction(13,encoded[12],43,op1=operand(2,0),
                           op2=operand(8,15,1)))
    ops.extend((instruction(14,250,62,op1=integer(1)),
                instruction(15,251,62,op1=integer(0))))
    mapping['opcodes']['6:250']=62
    mapping['opcodes']['7:251']=62
    return {'opcodes':ops,'compiled_vars':[],'loop_records':[]},mapping


class ThreeCallJoinTests(unittest.TestCase):
    def proof(self, group, mapping):
        return join_proofs(group['opcodes'],{},mapping).get(13)

    def test_calls_are_kept_in_short_circuit_order(self):
        group,mapping=fixture()
        proof=self.proof(group,mapping)
        self.assertTrue(proof['effectful_call_chain'])
        self.assertEqual(proof['expression'],
                         '((!first()) && (!second()) && third())')
        self.assertEqual(proof['shortcut_indices'],[4,9])
        body,audit=build_group(group,mapping,'<main>')
        self.assertEqual(len(audit['folded_short_circuits']),1)
        self.assertTrue(any(proof['expression'] in line for line in body))

    def test_wrong_shortcut_target_is_rejected(self):
        group,mapping=fixture()
        group['opcodes'][9]['op2']=operand(8,12,1)
        self.assertIsNone(self.proof(group,mapping))

    def test_wrong_call_result_slot_is_rejected(self):
        group,mapping=fixture()
        group['opcodes'][6]['result']=operand(4,8)
        self.assertIsNone(self.proof(group,mapping))

    def test_unconfirmed_key_is_rejected(self):
        group,mapping=fixture()
        group['opcodes'][10]['encoded_opcode']=252
        mapping['opcodes']['2:252']=59
        self.assertIsNone(self.proof(group,mapping))

    def test_external_consumer_is_rejected(self):
        group,mapping=fixture()
        group['opcodes'][14]=instruction(14,253,38,operand(16,0),operand(2,0),integer(1))
        mapping['opcodes']['6:253']=38
        self.assertIsNone(self.proof(group,mapping))


if __name__=='__main__':
    unittest.main()
