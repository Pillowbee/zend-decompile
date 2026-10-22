"""Algorithm checks on Python op arrays; these are not Encoder fixtures."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from zend_decompiler.crossblock import join_proofs, prove_cv_or_join
from zend_decompiler.prefix_restore import Decoder, Unsupported


def const_string(value: bytes):
    return {'type': 1, 'constant': {'kind': 'string', 'raw_hex': value.hex()}}


def node(kind: int, number: int = 0, other: int = 0):
    return {'type': kind, 'word0': number, 'word1': other}


def op(index, kind, result, left, right, *, encoded=None):
    return {'index': index, 'kind': kind, 'encoded_opcode': encoded,
            'result': result, 'op1': left, 'op2': right, 'extended_value': 0}


class KindDecoder(Decoder):
    def kind(self, instruction):
        return instruction['kind']


def object_ops():
    class_name = const_string(b'Example')
    return [
        op(0, 'NEW', node(4, 1), class_name, node(8, 0, 1)),
        op(1, 'INIT_FCALL_BY_NAME', node(8, 0, 1), node(4, 1), class_name),
        op(2, 'SEND_VAL', node(8, 0, 1), const_string(b'x'), node(8, 1, 1)),
        op(3, 'DO_FCALL_BY_NAME', node(4, 0), class_name, node(8, 0, 1)),
        op(4, 'ASSIGN', node(4, 2), node(16, 0), node(4, 1)),
        op(5, 'FETCH_OBJ_R', node(4, 3), node(16, 0), const_string(b'field')),
        op(6, 'ECHO', node(8, 0, 1), node(4, 3), node(8, 0, 1)),
        op(7, 'FETCH_OBJ_W', node(4, 4), node(16, 0), const_string(b'field')),
        op(8, 'ASSIGN', node(4, 5), node(4, 4), const_string(b'y')),
    ]


class ObjectDecodingTests(unittest.TestCase):
    def decode(self, instructions):
        return KindDecoder(instructions, {0: b'item'}, {'names': {}, 'opcodes': {}}).run(
            0, len(instructions)-1)

    def test_constructor_object_slot_and_property_read_write(self):
        segment = self.decode(object_ops())
        self.assertEqual(segment.statements, [
            b"$item = new Example('x');", b'echo $item->field;',
            b"$item->field = 'y';"])

    def test_unused_object_creation_preserves_one_side_effect(self):
        segment = self.decode(object_ops()[:4])
        self.assertEqual(segment.statements, [b"new Example('x');"])

    def test_constructor_name_mismatch_is_rejected(self):
        instructions = object_ops()
        instructions[1]['op2'] = const_string(b'Other')
        with self.assertRaisesRegex(Unsupported, 'Constructor does not match'):
            self.decode(instructions)

    def test_dangling_new_and_constructor_return_use_are_rejected(self):
        with self.assertRaisesRegex(Unsupported, 'NEW without constructor'):
            self.decode(object_ops()[:1])
        instructions = object_ops()[:4]
        instructions.append(op(4, 'ECHO', node(8, 0, 1), node(4, 0), node(8, 0, 1)))
        with self.assertRaisesRegex(Unsupported, 'Constructor return value'):
            self.decode(instructions)

    def test_invalid_property_name_is_rejected(self):
        instructions = object_ops()
        instructions[5]['op2'] = const_string(b'bad-name')
        with self.assertRaisesRegex(Unsupported, 'Non-simple PHP identifier'):
            self.decode(instructions)


def cv_or_ops():
    return [
        op(0, 'JMPNZ_EX', node(2, 0), node(16, 0), node(8, 2, 1), encoded=47),
        op(1, 'BOOL', node(2, 0), node(16, 1), node(8, 0, 1), encoded=52),
        op(2, 'JMPZ', node(8, 0, 1), node(2, 0), node(8, 4, 1), encoded=43),
        op(3, 'INIT_STRING', node(2, 0), node(8, 0, 1), node(8, 0, 1), encoded=53),
        op(4, 'RETURN', node(8, 0, 1),
           {'type': 1, 'constant': {'kind': 'null'}}, node(8, 0, 1), encoded=62),
    ]


OR_MAP = {'opcodes': {'0:47': 47, '1:52': 52, '2:43': 43,
                      '3:53': 53, '4:62': 62},
          'names': {'47': 'JMPNZ_EX', '52': 'BOOL', '43': 'JMPZ',
                    '53': 'INIT_STRING', '62': 'RETURN'}}


class CvOrProofTests(unittest.TestCase):
    def test_exact_diamond_produces_ordered_or(self):
        proof = prove_cv_or_join(cv_or_ops(), {0: b'width', 1: b'height'}, OR_MAP, 2)
        self.assertEqual(proof['expression'], '($width || $height)')
        self.assertEqual(proof['source_indices'], [0, 1, 2])

    def test_wrong_target_and_slot_are_rejected(self):
        instructions = cv_or_ops()
        instructions[0]['op2'] = node(8, 3, 1)
        with self.assertRaises(Unsupported):
            prove_cv_or_join(instructions, {0: b'width', 1: b'height'}, OR_MAP, 2)
        instructions = cv_or_ops()
        instructions[1]['result'] = node(2, 1)
        with self.assertRaises(Unsupported):
            prove_cv_or_join(instructions, {0: b'width', 1: b'height'}, OR_MAP, 2)

    def test_live_result_after_join_is_rejected(self):
        instructions = cv_or_ops()
        instructions[3]['result'] = node(2, 1)
        with self.assertRaises(Unsupported):
            prove_cv_or_join(instructions, {0: b'width', 1: b'height'}, OR_MAP, 2)


def and_or_ops():
    compare = lambda i, slot, cv, literal: op(
        i, 'IS_EQUAL', node(2, slot), node(16, cv), const_string(literal), encoded=17)
    instructions = [
        compare(0, 0, 0, b'x'),
        op(1, 'JMPZ_EX', node(2, 0), node(2, 0), node(8, 4, 1), encoded=46),
        compare(2, 1, 1, b'y'),
        op(3, 'BOOL', node(2, 0), node(2, 1), node(8, 0, 1), encoded=52),
        op(4, 'JMPNZ_EX', node(2, 0), node(2, 0), node(8, 10, 1), encoded=47),
        compare(5, 1, 0, b'x'),
        op(6, 'JMPZ_EX', node(2, 1), node(2, 1), node(8, 9, 1), encoded=46),
        compare(7, 2, 2, b'z'),
        op(8, 'BOOL', node(2, 1), node(2, 2), node(8, 0, 1), encoded=52),
        op(9, 'BOOL', node(2, 0), node(2, 1), node(8, 0, 1), encoded=52),
        op(10, 'JMPZ', node(8, 0, 1), node(2, 0), node(8, 12, 1), encoded=43),
        op(11, 'RETURN', node(8, 0, 1),
           {'type': 1, 'constant': {'kind': 'null'}}, node(8, 0, 1), encoded=62),
        op(12, 'RETURN', node(8, 0, 1),
           {'type': 1, 'constant': {'kind': 'null'}}, node(8, 0, 1), encoded=62),
    ]
    names = {'17': 'IS_EQUAL', '46': 'JMPZ_EX', '47': 'JMPNZ_EX',
             '52': 'BOOL', '43': 'JMPZ', '62': 'RETURN'}
    mapping = {'opcodes': {f"{item['index'] % 8}:{item['encoded_opcode']}":
                           item['encoded_opcode'] for item in instructions},
               'names': names}
    return instructions, mapping


class NestedAndOrTests(unittest.TestCase):
    def test_two_and_terms_keep_duplicate_reads_and_order(self):
        instructions, mapping = and_or_ops()
        proof = join_proofs(instructions, {0: b'a', 1: b'b', 2: b'c'}, mapping)[10]
        self.assertEqual(proof['expression'],
                         "((($a == 'x') && ($b == 'y')) || (($a == 'x') && ($c == 'z')))")
        self.assertEqual(proof['source_indices'], list(range(11)))
        self.assertEqual(len(proof['block_seeds']), 2)

    def test_wrong_outer_shortcut_does_not_get_composite_proof(self):
        instructions, mapping = and_or_ops()
        instructions[4]['op2'] = node(8, 9, 1)
        proofs = join_proofs(instructions, {0: b'a', 1: b'b', 2: b'c'}, mapping)
        self.assertFalse(proofs.get(10, {}).get('nested'))


if __name__ == '__main__':
    unittest.main()
