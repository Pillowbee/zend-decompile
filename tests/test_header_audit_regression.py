"""Independent header layout checks; never validate encoded semantics."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zend_assets import OPCODE_MAP, OPCODE_METADATA, GOLDEN, SCHEMAS, ALIGNMENT_FIXTURE, BATCH_REPORT_FIXTURE
from zend_header_audit import inspect_headers


class LegacyHeaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = ROOT / 'reference_headers_php52_candidate'

    def test_legacy_headers_recognized_without_claiming_exact_build(self):
        report = inspect_headers(self.reference)
        self.assertEqual(report['verdict'], 'php_5_2_family_layout_unverified_build')
        self.assertTrue(report['native_opcode_layout_matches_php_5_2_family'])
        self.assertFalse(report['exact_php_5_2_17_build_verified'])
        self.assertFalse(report['suitable_for_encoder_opcode_confirmation'])
        self.assertEqual(report['number_of_opcode_definitions'], 129)
        self.assertEqual(report['all_header_handler_mismatches'], [])
        self.assertEqual(report['duplicate_numeric_definitions'], [])
        self.assertEqual(report['status_updates'], {'confirmed':0, 'inferred':0, 'unknown':0})

    def test_opcode_49_and_140_agree_in_both_headers(self):
        result = inspect_headers(self.reference)['selected_native_opcode_numbers']
        for opcode, name in [(49, 'ZEND_SWITCH_FREE'),
                             (140, 'ZEND_DECLARE_INHERITED_CLASS')]:
            entry = result[str(opcode)]
            self.assertEqual(entry['header_definition']['name'], name)
            self.assertIn(name, [h['name'] for h in entry['vm_handlers']])
        self.assertIsNone(result['199']['header_definition'])
        self.assertEqual(result['199']['vm_handlers'], [])

    def test_mismatched_vm_handler_cannot_pass_compatibility(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder)
            for name in ('zend_compile.h','zend_vm_opcodes.h','zend_vm_def.h'):
                shutil.copy2(self.reference / name, dest / name)
            path = dest / 'zend_vm_def.h'
            data = path.read_bytes()
            old = b'ZEND_VM_HANDLER(140, ZEND_DECLARE_INHERITED_CLASS,'
            self.assertIn(old, data)
            path.write_bytes(data.replace(old, b'ZEND_VM_HANDLER(140, ZEND_MADE_UP_OPCODE,', 1))
            report = inspect_headers(dest)
            self.assertNotEqual(report['verdict'], 'php_5_2_family_layout_unverified_build')
            self.assertFalse(report['native_opcode_layout_matches_php_5_2_family'])
            self.assertTrue(any(m['opcode'] == 140 for m in report['all_header_handler_mismatches']))

    def test_audit_is_reproducible_and_does_not_modify_opcode_map(self):
        a = inspect_headers(self.reference)
        b = inspect_headers(self.reference)
        self.assertEqual(a, b)
        path = OPCODE_MAP
        expected = json.loads((OPCODE_METADATA).read_text(encoding='utf-8'))['mapping_sha256']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main()
