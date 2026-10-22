"""Field-level parser checks; synthetic rows do not establish Encoder format."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from zend_decompiler.serial_parser import (FormatError, decompress_encoded,
                                           parse_binary, validate_function_table_key)


KEY = b'\0fnmodule.php83'
NAME = b'fn'


def declaration(*, index: int = 146, line: int = 83, encoded_opcode: int = 252,
                key: bytes = KEY, name: bytes = NAME, extended: int = 2) -> dict:
    return {
        'index': index, 'line': line, 'encoded_opcode': encoded_opcode,
        'extended_value': extended,
        'result': {'type': 8, 'word0': 0, 'word1': 1},
        'op1': {'type': 1, 'constant': {'raw_hex': key.hex()}},
        'op2': {'type': 1, 'constant': {'raw_hex': name.hex()}},
    }


class FunctionTableKeyTests(unittest.TestCase):
    def test_legacy_nul_terminated_key_keeps_its_contract(self):
        validate_function_table_key(b'fn\0', NAME, [])

    def test_bounded_runtime_declaration_key(self):
        validate_function_table_key(KEY, NAME, [declaration()])

    def test_prefix_and_suffix_must_match_observed_form(self):
        for key in (b'fnmodule.php83', b'\0othermodule.php83',
                    b'\0fnmodule.php', b'\0fnmodule.php0',
                    b'\0fnmodule.php83\0tail', b'\0fn../module.php83',
                    b'\0fn' + b'x' * 250 + b'.php83'):
            with self.subTest(key=key), self.assertRaises(FormatError):
                validate_function_table_key(key, NAME, [declaration(key=key)])

    def test_declaration_line_and_operand_name_must_match(self):
        for row in (declaration(line=84), declaration(name=b'other'),
                    declaration(key=b'\0othermodule.php83')):
            with self.subTest(row=row), self.assertRaises(FormatError):
                validate_function_table_key(KEY, NAME, [row])

    def test_unobserved_opcode_or_operand_shape_is_rejected(self):
        rows = [declaration(encoded_opcode=251), declaration(index=147),
                declaration(extended=0)]
        wrong_result = declaration()
        wrong_result['result'] = {'type': 4, 'word0': 0, 'word1': 0}
        rows.append(wrong_result)
        for row in rows:
            with self.subTest(row=row), self.assertRaises(FormatError):
                validate_function_table_key(KEY, NAME, [row])

    def test_declaration_anchor_must_be_unique(self):
        with self.assertRaises(FormatError):
            validate_function_table_key(KEY, NAME, [declaration(), declaration()])

    def test_existing_real_control_input_still_parses(self):
        raw = decompress_encoded(ROOT / 'sample_inputs' / 'links_fun(1).php',
                                 (ROOT / 'zend_verified_dictionary.bin').read_bytes())[0][1]
        parsed = parse_binary(raw)
        self.assertEqual(parsed['consumed_bytes'], len(raw))
        self.assertEqual(len(parsed['functions']), 5)


if __name__ == '__main__':
    unittest.main()
