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
        self.assertIn('foreach binding outside a foreach fetch', str(caught.exception))

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


if __name__ == '__main__':
    unittest.main()
