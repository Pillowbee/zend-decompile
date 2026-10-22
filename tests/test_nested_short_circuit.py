"""A bounded nested CFG proof; synthetic op arrays do not establish Encoder format."""
from __future__ import annotations

import copy
import unittest

from zend_decompiler.cfg import cfg_for_group
from zend_decompiler.crossblock import join_proofs, proof_seeds_by_block
from zend_decompiler.prefix_restore import Unsupported
from zend_decompiler.restore_core import build_group


NATIVE = {'IS_EQUAL': 17, 'IS_NOT_EQUAL': 18, 'JMPZ': 43,
          'JMPZ_EX': 46, 'JMPNZ_EX': 47, 'BOOL': 52, 'RETURN': 62}


def slot(number):
    return {'type': 2, 'word0': number, 'word1': 0}


def cv(number):
    return {'type': 16, 'word0': number, 'word1': 0}


def integer(number):
    return {'type': 1, 'constant': {'kind': 'integer', 'value': number}}


def unused(number=0):
    return {'type': 8, 'word0': number, 'word1': 1}


def instruction(index, name, result=None, op1=None, op2=None):
    return {'index': index, 'encoded_opcode': 100 + index,
            'result': result or unused(), 'op1': op1 or unused(),
            'op2': op2 or unused(), 'extended_value': 0, 'line': index + 1,
            'decoded_opcode': NATIVE[name]}


def nested_group():
    # ($a == 1 || $b == 1) && ($c != 1) && ($d == 1 || $d == 2)
    ops = [
        instruction(0, 'IS_EQUAL', slot(0), cv(0), integer(1)),
        instruction(1, 'JMPNZ_EX', slot(0), slot(0), unused(4)),
        instruction(2, 'IS_EQUAL', slot(1), cv(1), integer(1)),
        instruction(3, 'BOOL', slot(0), slot(1)),
        instruction(4, 'JMPZ_EX', slot(0), slot(0), unused(13)),
        instruction(5, 'IS_NOT_EQUAL', slot(1), cv(2), integer(1)),
        instruction(6, 'BOOL', slot(0), slot(1)),
        instruction(7, 'JMPZ_EX', slot(0), slot(0), unused(13)),
        instruction(8, 'IS_EQUAL', slot(1), cv(3), integer(1)),
        instruction(9, 'JMPNZ_EX', slot(1), slot(1), unused(12)),
        instruction(10, 'IS_EQUAL', slot(2), cv(3), integer(2)),
        instruction(11, 'BOOL', slot(1), slot(2)),
        instruction(12, 'BOOL', slot(0), slot(1)),
        instruction(13, 'JMPZ', op1=slot(0), op2=unused(15)),
        instruction(14, 'RETURN', op1=integer(1)),
        instruction(15, 'RETURN', op1=integer(0)),
    ]
    group={'opcodes': ops, 'compiled_vars': [
        {'index': index, 'name_hex': name.hex()}
        for index, name in enumerate((b'a', b'b', b'c', b'd'))],
        'loop_records': []}
    mapping={'names': {str(number): name for name, number in NATIVE.items()},
             'opcodes': {f'{op["index"] % 8}:{op["encoded_opcode"]}':
                         op['decoded_opcode'] for op in ops}}
    return group, mapping


class NestedShortCircuitTests(unittest.TestCase):
    def proof(self, group, mapping):
        cvs={v['index']: bytes.fromhex(v['name_hex']) for v in group['compiled_vars']}
        return join_proofs(group['opcodes'], cvs, mapping)

    def test_composes_ordered_condition_and_emits_one_branch(self):
        group,mapping=nested_group()
        proofs=self.proof(group,mapping)
        self.assertEqual(list(proofs), [13])
        proof=proofs[13]
        self.assertTrue(proof['nested'])
        self.assertEqual(proof['expression'],
                         '((($a == 1) || ($b == 1)) && ($c != 1) && '
                         '(($d == 1) || ($d == 2)))')
        self.assertEqual(proof['source_indices'], list(range(14)))
        blocks=cfg_for_group('<main>',group)['basic_blocks']
        seeds=proof_seeds_by_block(proofs,blocks)
        self.assertEqual(set(seeds), {4, 12, 13})
        body,audit=build_group(group,mapping,'<main>')
        self.assertEqual(len(audit['folded_short_circuits']), 1)
        self.assertTrue(any(proof['expression'] in line for line in body))

    def test_changed_and_target_does_not_compose(self):
        group,mapping=nested_group()
        group['opcodes'][7]['op2']=unused(12)
        self.assertFalse(self.proof(group,mapping)[13].get('nested',False))
        with self.assertRaises(Unsupported):
            build_group(group,mapping,'<main>')

    def test_changed_inner_or_target_does_not_compose(self):
        group,mapping=nested_group()
        group['opcodes'][1]['op2']=unused(3)
        self.assertFalse(self.proof(group,mapping)[13].get('nested',False))

    def test_foreign_temporary_does_not_compose(self):
        group,mapping=nested_group()
        group['opcodes'][7]['result']=slot(9)
        self.assertFalse(self.proof(group,mapping)[13].get('nested',False))
        with self.assertRaises(Unsupported):
            build_group(group,mapping,'<main>')

    def test_effectful_middle_instruction_does_not_compose(self):
        group,mapping=nested_group()
        group['opcodes'][5]['decoded_opcode']=38  # ASSIGN
        mapping['names']['38']='ASSIGN'
        mapping['opcodes']['5:105']=38
        self.assertFalse(self.proof(group,mapping)[13].get('nested',False))

    def test_intermediate_seed_requires_a_block_entry(self):
        group,mapping=nested_group()
        proofs=self.proof(group,mapping)
        blocks=copy.deepcopy(cfg_for_group('<main>',group)['basic_blocks'])
        seed_block=next(b for b in blocks if b['first']==12)
        seed_block['first']=11
        with self.assertRaisesRegex(Unsupported,'block entry'):
            proof_seeds_by_block(proofs,blocks)


if __name__=='__main__':
    unittest.main()
