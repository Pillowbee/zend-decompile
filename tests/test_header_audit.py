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
    def test_uploaded_modern_headers_rejected_when_available(self):
        uploaded=ROOT/'reference_headers_incompatible'
        if not all((uploaded/name).exists() for name in ('zend_vm_opcodes.h','zend_vm_def.h','zend_compile.h')):
            self.skipTest('Uploaded headers not in runtime')
        report=inspect_headers(uploaded)
        self.assertEqual(report['verdict'],'incompatible_with_php_5_2')
        self.assertEqual(report['selected_native_opcode_numbers']['140']['header_definition']['name'],'ZEND_MAKE_REF')
        self.assertEqual(report['selected_native_opcode_numbers']['49']['header_definition']['name'],'ZEND_CHECK_VAR')
        self.assertEqual(report['selected_native_opcode_numbers']['199']['header_definition']['name'],'ZEND_CHECK_UNDEF_ARGS')
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
