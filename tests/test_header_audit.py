"""Headers cannot authorize opcode renumbering unless exact PHP version is proved."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from zend_decompiler.assets import OPCODE_MAP, OPCODE_METADATA, GOLDEN, SCHEMAS, ALIGNMENT_FIXTURE, BATCH_REPORT_FIXTURE
from zend_decompiler.header_audit import inspect_headers

class HeaderAuditTests(unittest.TestCase):
    def test_known_modern_headers_rejected_without_archiving_second_header_tree(self):
        # The original modern header audit remains an immutable research record.
        # Minimal temporary *header* snippets exercise the rejection algorithm;
        # they are not PHP source fixtures or opcode-mapping evidence.
        archived=json.loads((ROOT/'data'/'research'/'header_audits.json').read_text(encoding='utf-8'))
        historical=archived['records']['incompatible_headers']
        self.assertEqual(historical['verdict'],'incompatible_with_php_5_2')
        modern={49:'ZEND_CHECK_VAR',140:'ZEND_MAKE_REF',199:'ZEND_CHECK_UNDEF_ARGS'}
        for value,name in modern.items():
            self.assertEqual(historical['selected_native_opcode_numbers'][str(value)]
                             ['header_definition']['name'],name)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'zend_vm_opcodes.h').write_text(
                '#define ZEND_NOP 0\n'
                '#define ZEND_CHECK_VAR 49\n'
                '#define ZEND_MAKE_REF 140\n'
                '#define ZEND_CHECK_UNDEF_ARGS 199\n'
                '#define ZEND_MATCH 200\n'
                '#define ZEND_VM_LAST_OPCODE 201\n',
                encoding='utf-8')
            (root/'zend_vm_def.h').write_text(
                'ZEND_VM_HANDLER(49, ZEND_CHECK_VAR, ANY)\n'
                'ZEND_VM_HANDLER(140, ZEND_MAKE_REF, ANY)\n'
                'ZEND_MATCH\n',encoding='utf-8')
            (root/'zend_compile.h').write_text(
                'typedef struct zend_ast zend_ast;\n'
                'zend_string *name;\n',encoding='utf-8')
            report=inspect_headers(root)
        self.assertEqual(report['verdict'],'incompatible_with_php_5_2')
        self.assertFalse(report['native_opcode_layout_matches_php_5_2_family'])
        for value,name in modern.items():
            self.assertEqual(report['selected_native_opcode_numbers'][str(value)]
                             ['header_definition']['name'],name)
        self.assertTrue(any(f['modern_markers'] for f in report['files'].values()))
        self.assertFalse(report['suitable_for_encoder_opcode_confirmation'])
        self.assertEqual(report['status_updates']['confirmed'],0)
    def test_missing_headers_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            report=inspect_headers(Path(folder))
            self.assertEqual(report['verdict'],'incomplete_headers')
            self.assertFalse(report['suitable_for_encoder_opcode_confirmation'])
    def test_absence_of_modern_features_is_not_proof_of_php52(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('zend_vm_opcodes.h','zend_vm_def.h','zend_compile.h'):
                (root/name).write_text('/* sample stub */\n',encoding='utf-8')
            report=inspect_headers(root)
            self.assertEqual(report['verdict'],'unverified_version')
            self.assertFalse(report['suitable_for_encoder_opcode_confirmation'])
    def test_mapping_not_modified(self):
        path=OPCODE_MAP
        meta=json.loads((OPCODE_METADATA).read_text(encoding='utf-8'))
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),meta['mapping_sha256'])

if __name__=='__main__':unittest.main()
