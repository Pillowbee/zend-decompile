"""Foreach reconstruction and the reference assignment of a variable variable.

The native PHP 5.2 shape of a foreach is known from the compile-only probe of
the own corpus: FE_RESET, FE_FETCH, OP_DATA, ASSIGN (by value) or
FE_RESET, FE_FETCH, OP_DATA, ASSIGN_REF (by reference).  The encoded stream
carries the binding in one instruction instead of two, and the decoder
reconstructs the construct from the pattern, never from a guess.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from zend_decompiler.assets import DICTIONARY, OPCODE_MAP
from zend_decompiler.calibrate import choose_opcode
from zend_decompiler.cfg import cfg_for_group
from zend_decompiler.encoder_foreach import foreach_fetches, foreach_markers
from zend_decompiler.engine import restore_result
from zend_decompiler.prefix_restore import FOREACH_VALUE, Decoder, Unsupported
from zend_decompiler.serial_parser import decompress_encoded, parse_binary

MAPPING = json.loads(OPCODE_MAP.read_text(encoding='utf-8'))


def parsed_file(name: str) -> dict:
    streams = decompress_encoded(ROOT / 'sample_inputs' / name, DICTIONARY.read_bytes())
    assert len(streams) == 1
    return parse_binary(streams[0][1])


def group_of(parsed: dict, name: str) -> dict:
    for function in parsed['functions']:
        if bytes.fromhex(function['name_hex']).decode('cp1251') == name:
            return function
    raise AssertionError('no group ' + name)


class ForeachReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsed = parsed_file('fun_all.php')

    def test_out_price_is_restored_with_a_foreach(self):
        result = restore_result(ROOT / 'sample_inputs' / 'fun_all.php', DICTIONARY, OPCODE_MAP)
        self.assertEqual(result.status, 'candidate_generated', result.reason)
        code = result.code.decode('cp1251')
        self.assertIn('foreach ($currency as &$row) {', code)
        self.assertIn('foreach ($ar as &$c) {', code)

    def test_the_foreach_carries_the_array_and_the_variable(self):
        result = restore_result(ROOT / 'sample_inputs' / 'fun_all.php', DICTIONARY, OPCODE_MAP)
        constructs = []
        for group in result.audit['groups']:
            constructs.extend(group.get('foreach_constructs') or [])
        self.assertEqual(len(constructs), 2)
        self.assertEqual({(c['array'], c['variable'], c['by_ref']) for c in constructs},
                         {('$currency', '$row', True), ('$ar', '$c', True)})

    def test_the_element_value_never_leaks_into_the_output(self):
        result = restore_result(ROOT / 'sample_inputs' / 'fun_all.php', DICTIONARY, OPCODE_MAP)
        self.assertNotIn(FOREACH_VALUE.decode(), result.code.decode('cp1251'))

    def test_the_foreach_header_is_a_loop_header(self):
        group = group_of(self.parsed, 'uc_rus')
        for op in group['opcodes']:
            op['decoded_opcode'] = choose_opcode(op, MAPPING)
        cfg = cfg_for_group('uc_rus', group)
        headers = [b for b in cfg['basic_blocks']
                   if b['first'] <= 16 <= b['last']]
        self.assertEqual(len(headers), 1)
        kinds = sorted(e['kind'] for e in headers[0]['successors'])
        self.assertEqual(kinds, ['nonzero', 'zero'])
        self.assertEqual([e['target_instruction'] for e in headers[0]['successors']], [46, 17])


class ForeachFailClosedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsed = parsed_file('fun_all.php')

    def _decoder(self, group, context=None):
        for op in group['opcodes']:
            op['decoded_opcode'] = choose_opcode(op, MAPPING)
        cvs = {v['index']: bytes.fromhex(v['name_hex']) for v in group['compiled_vars']}
        return Decoder(group['opcodes'], cvs, MAPPING, None, None,
                       context if context is not None else {})

    def test_a_fetch_without_a_reset_is_refused(self):
        group = group_of(self.parsed, 'uc_rus')
        decoder = self._decoder(group)
        with self.assertRaises(Unsupported) as caught:
            decoder.run(16, 16)
        self.assertIn('foreach fetch without a reset', str(caught.exception))

    def test_a_binding_outside_a_fetch_is_refused(self):
        group = group_of(self.parsed, 'uc_rus')
        decoder = self._decoder(group)
        with self.assertRaises(Unsupported) as caught:
            decoder.run(17, 17)
        # Outside a fetch the instruction has no known native opcode and no
        # recognised structure, so the block is refused.
        self.assertIn('Unknown opcode', str(caught.exception))

    def test_a_fetch_of_a_foreign_iterator_is_refused(self):
        group = group_of(self.parsed, 'uc_rus')
        context = {}
        decoder = self._decoder(group, context)
        decoder.run(15, 15)          # the reset
        ops = group['opcodes']
        ops[16]['op1'] = {'type': 4, 'word0': 9, 'word1': 0}
        decoder = self._decoder(group, context)
        with self.assertRaises(Unsupported) as caught:
            decoder.run(16, 16)
        self.assertIn('foreign iterator', str(caught.exception))


class VariableVariableTests(unittest.TestCase):
    """FETCH_W over a compiled variable is a variable variable."""

    @classmethod
    def setUpClass(cls):
        cls.parsed = parsed_file('fun_all.php')

    def test_out_field_restores_the_reference_assignment(self):
        result = restore_result(ROOT / 'sample_inputs' / 'fun_all.php', DICTIONARY, OPCODE_MAP)
        self.assertEqual(result.status, 'candidate_generated', result.reason)
        code = result.code.decode('cp1251')
        self.assertIn('$$name_field = &$$name_field;', code)

    def test_the_global_statement_keeps_its_own_form(self):
        result = restore_result(ROOT / 'sample_inputs' / 'fun_all.php', DICTIONARY, OPCODE_MAP)
        code = result.code.decode('cp1251')
        self.assertIn('global $connect_mysql;', code)

    def test_a_fetch_w_of_an_unknown_shape_is_refused(self):
        group = group_of(self.parsed, 'out_field')
        for op in group['opcodes']:
            op['decoded_opcode'] = choose_opcode(op, MAPPING)
        cvs = {v['index']: bytes.fromhex(v['name_hex']) for v in group['compiled_vars']}
        cfg = cfg_for_group('out_field', group)
        block = next(b for b in cfg['basic_blocks'] if b['first'] <= 23 <= b['last'])
        ops = group['opcodes']
        original = ops[23]['op1']
        try:
            ops[23]['op1'] = {'type': 2, 'word0': 0, 'word1': 0}
            decoder = Decoder(ops, cvs, MAPPING)
            with self.assertRaises(Unsupported) as caught:
                decoder.run(block['first'], block['last'])
            self.assertIn('Complex FETCH_W unsupported', str(caught.exception))
        finally:
            ops[23]['op1'] = original


class StructuralForeachFetchTests(unittest.TestCase):
    """The fetch may have no established native opcode; it is recognised by shape."""

    @staticmethod
    def unused(value=0, marker=1):
        return {'type': 8, 'word0': value, 'word1': marker}

    @staticmethod
    def temporary(number=0, kind=2):
        return {'type': kind, 'word0': number, 'word1': 0}

    @staticmethod
    def compiled_variable(number=0):
        return {'type': 16, 'word0': number, 'word1': 0}

    def ops(self):
        unused, temporary = self.unused, self.temporary
        return [
            {'index': 0, 'encoded_opcode': 100, 'line': 1, 'extended_value': 0,
             'op1': self.compiled_variable(0), 'op2': unused(),
             'result': temporary(0)},
            {'index': 1, 'encoded_opcode': 101, 'line': 2, 'extended_value': 0,
             'op1': temporary(0), 'op2': unused(4), 'result': temporary(1)},
            {'index': 2, 'encoded_opcode': 102, 'line': 3, 'extended_value': 0,
             'op1': temporary(1), 'op2': unused(),
             'result': temporary(0, kind=4)},
            {'index': 3, 'encoded_opcode': 103, 'line': 4, 'extended_value': 0,
             'op1': self.compiled_variable(1), 'op2': temporary(0, kind=4),
             'result': temporary(2)},
        ]

    @staticmethod
    def mapping():
        # Only the reset and the assignment are mapped; the fetch and the
        # binding must be recognised without an opcode number.
        return {'names': {'77': 'FE_RESET', '38': 'ASSIGN'},
                'opcodes': {'0:100': 77, '3:103': 38}}

    def decoder(self, ops, context=None):
        return Decoder(ops, {0: b'arr', 1: b'v'}, self.mapping(),
                       context=context if context is not None else {})

    def test_fetch_and_binding_are_recognised_by_shape(self):
        ops = self.ops()
        self.assertEqual(foreach_fetches(ops, self.mapping()), {1})
        self.assertEqual(foreach_markers(ops, self.mapping()), {2})
        context = {}
        segment = self.decoder(ops, context).run(0, 3)
        self.assertEqual(segment.statements, [])
        self.assertEqual(segment.branch, ('FE_FETCH', b'', 4))
        self.assertEqual(context['foreach']['variable'], b'$v')
        self.assertEqual(context['foreach']['stage'], 'bound')
        self.assertEqual(segment.fired_rules.get('FOREACH_FETCH'), 1)
        self.assertEqual(segment.fired_rules.get('FOREACH_BINDING'), 1)

    def test_a_known_fetch_opcode_is_not_recognised_structurally(self):
        ops = self.ops()
        mapping = self.mapping()
        mapping['opcodes']['1:101'] = 78
        self.assertEqual(foreach_fetches(ops, mapping), set())

    def test_a_fetch_of_a_foreign_iterator_is_not_recognised(self):
        ops = self.ops()
        ops[1]['op1'] = self.temporary(9)
        with self.assertRaisesRegex(Unsupported, 'Unknown opcode #1'):
            self.decoder(ops).run(0, 3)

    def test_a_fetch_that_does_not_produce_a_temporary_is_not_recognised(self):
        ops = self.ops()
        ops[1]['result'] = self.temporary(1, kind=4)
        with self.assertRaisesRegex(Unsupported, 'Unknown opcode #1'):
            self.decoder(ops).run(0, 3)

    def test_a_fetch_without_a_reset_is_not_recognised(self):
        with self.assertRaisesRegex(Unsupported, 'Unknown opcode #1'):
            self.decoder(self.ops()).run(1, 3)

    def test_a_binding_without_a_fetch_is_not_recognised(self):
        ops = self.ops()
        decoder = self.decoder(ops)
        decoder.run(0, 0)             # the reset
        with self.assertRaisesRegex(Unsupported, 'Unknown opcode #2'):
            decoder.run(2, 3)


if __name__ == '__main__':
    unittest.main()
