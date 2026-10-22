"""Bounded CFG algorithm tests; synthetic op arrays are not Encoder evidence."""
from __future__ import annotations

import json
import unittest

from zend_decompiler.assets import OPCODE_MAP
from zend_decompiler.crossblock import join_proofs
from zend_decompiler.restore_core import build_group


def node(kind, number=0, other=0):
    return {'type': kind, 'word0': number, 'word1': other}


def literal(value):
    return {'type': 1, 'constant': {'kind': 'string',
                                   'raw_hex': value.encode().hex()}}


def instruction(index, encoded, native, result=None, op1=None, op2=None):
    return {'index': index, 'encoded_opcode': encoded,
            'decoded_opcode': native, 'result': result or node(8),
            'op1': op1 or node(8), 'op2': op2 or node(8),
            'extended_value': 0, 'line': index+1}


def fixture():
    mapping=json.loads(OPCODE_MAP.read_text(encoding='utf-8'))
    # These nine committed evidence keys are independently marked confirmed.
    encoded=[38,229,8,65,228,231,96,107,161]
    native=[81,81,18,46,81,81,18,52,43]
    ops=[
        instruction(0,encoded[0],native[0],node(4,0),node(16,0),node(16,1)),
        instruction(1,encoded[1],native[1],node(4,1),node(16,2),node(4,0)),
        instruction(2,encoded[2],native[2],node(2,0),node(4,1),literal('a')),
        instruction(3,encoded[3],native[3],node(2,0),node(2,0),node(8,8,1)),
        instruction(4,encoded[4],native[4],node(4,1),node(16,0),node(16,1)),
        instruction(5,encoded[5],native[5],node(4,2),node(16,2),node(4,1)),
        instruction(6,encoded[6],native[6],node(2,1),node(4,2),literal('b')),
        instruction(7,encoded[7],native[7],node(2,0),node(2,1)),
        instruction(8,encoded[8],native[8],op1=node(2,0),op2=node(8,10,1)),
        instruction(9,250,62,op1={'type':1,'constant':{'kind':'integer','value':1}}),
        instruction(10,251,62,op1={'type':1,'constant':{'kind':'integer','value':0}}),
    ]
    mapping['opcodes']['1:250']=62
    mapping['opcodes']['2:251']=62
    group={'opcodes':ops,'compiled_vars':[
        {'index':i,'name_hex':name.hex()}
        for i,name in enumerate((b'inner',b'key',b'outer'))],
        'loop_records':[]}
    return group,mapping


class NestedDimensionJoinTests(unittest.TestCase):
    def proof(self, group, mapping):
        cvs={v['index']:bytes.fromhex(v['name_hex']) for v in group['compiled_vars']}
        return join_proofs(group['opcodes'],cvs,mapping).get(8)

    def test_both_reads_are_rendered_in_original_short_circuit_order(self):
        group,mapping=fixture()
        proof=self.proof(group,mapping)
        self.assertTrue(proof['nested_dimension_reads'])
        self.assertEqual(proof['source_indices'],list(range(9)))
        self.assertEqual(proof['expression'],
                         "(($outer[$inner[$key]] != 'a') && "
                         "($outer[$inner[$key]] != 'b'))")
        body,audit=build_group(group,mapping,'<main>')
        self.assertEqual(len(audit['folded_short_circuits']),1)
        self.assertTrue(any(proof['expression'] in line for line in body))

    def test_wrong_inner_slot_is_rejected(self):
        group,mapping=fixture()
        group['opcodes'][5]['op2']=node(4,9)
        self.assertIsNone(self.proof(group,mapping))

    def test_different_shortcut_target_is_rejected(self):
        group,mapping=fixture()
        group['opcodes'][3]['op2']=node(8,7,1)
        self.assertIsNone(self.proof(group,mapping))

    def test_unconfirmed_opcode_key_is_rejected(self):
        group,mapping=fixture()
        group['opcodes'][4]['encoded_opcode']=252
        mapping['opcodes']['4:252']=81
        self.assertIsNone(self.proof(group,mapping))

    def test_external_consumer_of_first_read_is_rejected(self):
        group,mapping=fixture()
        group['opcodes'][9]=instruction(9,252,40,op1=node(4,1))
        mapping['opcodes']['1:252']=40
        self.assertIsNone(self.proof(group,mapping))

    def test_extra_entry_into_second_read_is_rejected(self):
        group,mapping=fixture()
        # Eight instructions retain every confirmed position-dependent key.
        # The entry branch reaches the second term without reading the first.
        prefix=[instruction(0,253,42,op1=node(8,12,1))]
        mapping['opcodes']['0:253']=42
        for i in range(1,8):
            prefix.append(instruction(i,253+i,0))
            mapping['opcodes'][f'{i}:{253+i}']=0
        for op in group['opcodes']:op['index']+=8
        group['opcodes'][3]['op2']=node(8,16,1)
        group['opcodes'][8]['op2']=node(8,18,1)
        group['opcodes']=prefix+group['opcodes']
        cvs={v['index']:bytes.fromhex(v['name_hex']) for v in group['compiled_vars']}
        self.assertIsNone(join_proofs(group['opcodes'],cvs,mapping).get(16))


if __name__=='__main__':
    unittest.main()
