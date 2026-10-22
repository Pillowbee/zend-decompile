"""Field-level checks only; these records are not fabricated Encoder streams."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from zend_decompiler.serial_parser import (FormatError, decompress_encoded,
                                           parse_binary, validate_experimental_class_section)


def observed_shape() -> tuple[dict, dict]:
    name = b'Example'
    key = name + b'\0'
    method = {'name_hex':name.hex(), 'tag':2, 'kind':1, 'flag':1}
    record = {'tag':1, 'key_hex':key.hex(), 'name_hex':name.hex(),
              'flag':4, 'count':1, 'reserved':0,
              'members':[{'tag':1, 'name_hex':b'field\0'.hex(), 'flag':0,
                          'count':1, 'reserved':0}],
              'closing_key_hex':key.hex(), 'closing_numbers':[0, 0, -1]}
    return method, record


class ExperimentalClassSectionTests(unittest.TestCase):
    def test_observed_field_relationships(self):
        validate_experimental_class_section(*observed_shape())

    def test_wrong_group_kind_or_header_is_rejected(self):
        for key, value in [('tag', 1), ('kind', 2), ('flag', 0),
                           ('name_hex', b'bad-name'.hex())]:
            method, record = observed_shape()
            method[key] = value
            with self.subTest(key=key), self.assertRaises(FormatError):
                validate_experimental_class_section(method, record)

    def test_mismatched_class_keys_and_closing_fields_are_rejected(self):
        for key, value in [('key_hex', b'Other\0'.hex()),
                           ('name_hex', b'Other'.hex()),
                           ('closing_key_hex', b'Other\0'.hex()),
                           ('closing_numbers', [0, 0, 0]), ('count', 2)]:
            method, record = observed_shape()
            record[key] = value
            with self.subTest(key=key), self.assertRaises(FormatError):
                validate_experimental_class_section(method, record)

    def test_member_shape_and_duplicate_names_are_rejected(self):
        for key, value in [('tag', 2), ('name_hex', b'field'.hex()),
                           ('flag', 1), ('count', 0), ('reserved', 1)]:
            method, record = observed_shape()
            record['members'][0][key] = value
            with self.subTest(key=key), self.assertRaises(FormatError):
                validate_experimental_class_section(method, record)
        method, record = observed_shape()
        record['members'].append(copy.deepcopy(record['members'][0]))
        with self.assertRaises(FormatError):
            validate_experimental_class_section(method, record)
        record['members'] = []
        with self.assertRaises(FormatError):
            validate_experimental_class_section(method, record)

    def test_committed_control_input_has_no_class_section(self):
        raw = decompress_encoded(ROOT / 'sample_inputs' / 'links_fun(1).php',
                                 (ROOT / 'zend_verified_dictionary.bin').read_bytes())[0][1]
        parsed = parse_binary(raw)
        self.assertEqual(parsed['consumed_bytes'], len(raw))
        self.assertEqual(parsed['experimental_method_groups'], [])
        self.assertEqual(parsed['experimental_class_records'], [])


if __name__ == '__main__':
    unittest.main()
