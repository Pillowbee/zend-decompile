"""Synthetic op_array algorithm tests; these do not establish Encoder format."""
from __future__ import annotations

import copy
import unittest

from zend_decompiler.bounded_and import bounded_and_proofs
from zend_decompiler.prefix_restore import Decoder, Unsupported


NATIVE = {'IS_NOT_EQUAL': 18, 'JMPZ_EX': 46, 'BOOL': 52, 'JMPZ': 43,
          'RETURN': 62, 'INIT_FCALL_BY_NAME': 59, 'CONCAT': 8,
          'SEND_VAL': 65, 'DO_FCALL_BY_NAME': 61, 'DECLARE_FUNCTION': 141}


def tmp(n): return {'type': 2, 'word0': n, 'word1': 0}
def var(n): return {'type': 4, 'word0': n, 'word1': 0}
def cv(n): return {'type': 16, 'word0': n, 'word1': 0}
def unused(n=0): return {'type': 8, 'word0': n, 'word1': 1}
def string(s): return {'type': 1, 'constant': {'kind': 'string', 'raw_hex': s.encode().hex()}}
def number(n): return {'type': 1, 'constant': {'kind': 'integer', 'value': n}}


def op(i, kind, a=None, b=None, r=None, ext=0):
    return {'index': i, 'encoded_opcode': 100 + i, 'decoded_opcode': NATIVE[kind],
            'op1': a if a is not None else unused(),
            'op2': b if b is not None else unused(),
            'result': r if r is not None else unused(),
            'extended_value': ext, 'line': i + 1}


def fixtures():
    # Three simple terms, then the two nested five-term/call layouts.
    simple = [
        op(0, 'IS_NOT_EQUAL', cv(0), string(''), tmp(0)),
        op(1, 'JMPZ_EX', tmp(0), unused(6), tmp(0)),
        op(2, 'IS_NOT_EQUAL', cv(1), string(''), tmp(1)),
        op(3, 'BOOL', tmp(1), r=tmp(0)),
        op(4, 'JMPZ_EX', tmp(0), unused(6), tmp(0)),
        op(5, 'BOOL', cv(2), r=tmp(0)),
        op(6, 'JMPZ', tmp(0), unused(8)),
        op(7, 'RETURN', number(1)), op(8, 'RETURN', number(0)),
    ]
    nested = [
        op(0, 'IS_NOT_EQUAL', cv(0), string(''), tmp(0)),
        op(1, 'JMPZ_EX', tmp(0), unused(13), tmp(0)),
        op(2, 'IS_NOT_EQUAL', cv(1), string(''), tmp(1)),
        op(3, 'JMPZ_EX', tmp(1), unused(6), tmp(1)),
        op(4, 'IS_NOT_EQUAL', cv(1), string('x'), tmp(2)),
        op(5, 'BOOL', tmp(2), r=tmp(1)),
        op(6, 'BOOL', tmp(1), r=tmp(0)),
        op(7, 'JMPZ_EX', tmp(0), unused(13), tmp(0)),
        op(8, 'IS_NOT_EQUAL', cv(2), string(''), tmp(1)),
        op(9, 'JMPZ_EX', tmp(1), unused(12), tmp(1)),
        op(10, 'IS_NOT_EQUAL', cv(2), string('y'), tmp(2)),
        op(11, 'BOOL', tmp(2), r=tmp(1)),
        op(12, 'BOOL', tmp(1), r=tmp(0)),
        op(13, 'JMPZ', tmp(0), unused(15)),
        op(14, 'RETURN', number(1)), op(15, 'RETURN', number(0)),
    ]
    call = [
        op(0, 'INIT_FCALL_BY_NAME', b=string('is_dir')),
        op(1, 'CONCAT', cv(0), cv(1), tmp(2)),
        op(2, 'SEND_VAL', tmp(2), unused(1), ext=61),
        op(3, 'DO_FCALL_BY_NAME', string('is_dir'), r=var(0), ext=1),
        op(4, 'JMPZ_EX', var(0), unused(10), tmp(2)),
        op(5, 'IS_NOT_EQUAL', cv(1), string('..'), tmp(3)),
        op(6, 'BOOL', tmp(3), r=tmp(2)),
        op(7, 'JMPZ_EX', tmp(2), unused(10), tmp(2)),
        op(8, 'IS_NOT_EQUAL', cv(1), string('.'), tmp(3)),
        op(9, 'BOOL', tmp(3), r=tmp(2)),
        op(10, 'JMPZ', tmp(2), unused(12)),
        op(11, 'RETURN', number(1)), op(12, 'RETURN', number(0)),
    ]
    return simple, nested, call


def settings(ops):
    mapping = {'names': {str(v): k for k, v in NATIVE.items()},
               'opcodes': {f'{o["index"] % 8}:{o["encoded_opcode"]}':
                           o['decoded_opcode'] for o in ops}}
    evidence = {key: {'status': 'confirmed', 'opcode': value}
                for key, value in mapping['opcodes'].items()}
    cvs = {i: bytes([ord('a') + i]) for i in range(3)}
    return mapping, evidence, cvs


class BoundedAndTests(unittest.TestCase):
    def proof(self, ops):
        mapping, evidence, cvs = settings(ops)
        return bounded_and_proofs(ops, cvs, mapping, evidence)

    def test_three_supported_shapes_keep_order_and_conditional_call(self):
        simple, nested, call = fixtures()
        for ops, join, count in ((simple, 6, 3), (nested, 13, 5), (call, 10, 3)):
            with self.subTest(join=join):
                proof = self.proof(ops)[join]
                self.assertTrue(proof['bounded_and_truth_table'])
                self.assertEqual(proof['comparison_count'], count)
                self.assertEqual(proof['source_indices'], list(range(join + 1)))
                self.assertEqual(len(proof['call_sites']), 1 if ops is call else 0)
        self.assertEqual([x['instruction_index'] for x in self.proof(nested)[13]['block_seeds']],
                         [6, 12])

    def test_changed_shortcut_target_refuses(self):
        _, nested, _ = fixtures()
        nested[3]['op2'] = unused(5)
        self.assertNotIn(13, self.proof(nested))

    def test_changed_temporary_refuses(self):
        simple, _, _ = fixtures()
        simple[4]['op1'] = tmp(9)
        self.assertNotIn(6, self.proof(simple))

    def test_external_consumer_refuses(self):
        simple, _, _ = fixtures()
        simple[7] = op(7, 'BOOL', tmp(0), r=tmp(3))
        self.assertNotIn(6, self.proof(simple))

    def test_unconfirmed_key_refuses(self):
        _, _, call = fixtures()
        mapping, evidence, cvs = settings(call)
        evidence['4:104']['status'] = 'unknown'
        self.assertNotIn(10, bounded_and_proofs(call, cvs, mapping, evidence))

    def test_changed_call_arity_refuses(self):
        _, _, call = fixtures()
        call[3]['extended_value'] = 2
        self.assertNotIn(10, self.proof(call))


class RuntimeDeclarationTests(unittest.TestCase):
    def test_exact_declaration_key_and_location_are_required(self):
        key = b'\0fsource.php7'
        instruction = op(0, 'DECLARE_FUNCTION', string(key.decode('latin1')),
                         string('f'), ext=2)
        # Build raw bytes directly, because the function-table key contains NUL.
        instruction['op1']['constant']['raw_hex'] = key.hex()
        context = {'declarations': {0: {'key': key, 'name': b'f',
                                        'marker': b'__DECL__'}}}
        mapping, _, _ = settings([instruction])
        result = Decoder([instruction], {}, mapping, context=context).run(0, 0)
        self.assertEqual(result.statements, [b'__DECL__'])
        altered = copy.deepcopy(instruction)
        altered['op1']['constant']['raw_hex'] = b'\0fsource.php8'.hex()
        with self.assertRaisesRegex(Unsupported, 'Unproved runtime'):
            Decoder([altered], {}, mapping, context=context).run(0, 0)
        with self.assertRaisesRegex(Unsupported, 'Unproved runtime'):
            Decoder([instruction], {}, mapping).run(0, 0)


if __name__ == '__main__': unittest.main()
