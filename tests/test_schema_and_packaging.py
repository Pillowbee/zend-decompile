from __future__ import annotations
import importlib.util,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from zend_decompiler.assets import OPCODE_MAP, OPCODE_METADATA, GOLDEN, SCHEMAS, ALIGNMENT_FIXTURE, BATCH_REPORT_FIXTURE
from zend_decompiler.engine import restore_result
from zend_decompiler.compiler_oracle import read_probe_log

class SchemaPackaging(unittest.TestCase):
    def test_new_schemas_on_real_samples(self):
        if importlib.util.find_spec('jsonschema') is None:
            self.skipTest('Optional jsonschema validation library unavailable')
        import jsonschema
        schema_root=ROOT/'schemas'
        batch=json.loads((BATCH_REPORT_FIXTURE).read_text())
        jsonschema.validate(batch,json.loads((SCHEMAS/'batch_report.schema.json').read_text()))
        for n in ('basket.php','fun_all.php'):
            audit=restore_result(ROOT/'sample_inputs'/n,ROOT/'zend_verified_dictionary.bin',OPCODE_MAP).audit
            jsonschema.validate(audit,json.loads((SCHEMAS/'audit.schema.json').read_text()))
        meta=json.loads((OPCODE_METADATA).read_text())
        jsonschema.validate(meta,json.loads((SCHEMAS/'opcode_metadata.schema.json').read_text()))

    def test_current_data_paths_exist(self):
        self.assertTrue(OPCODE_MAP.is_file())
        self.assertTrue(OPCODE_METADATA.is_file())
        self.assertTrue(ALIGNMENT_FIXTURE.is_file())
        self.assertTrue(BATCH_REPORT_FIXTURE.is_file())

    def test_active_mapping_metadata_is_consistent(self):
        import hashlib
        metadata = json.loads(OPCODE_METADATA.read_text(encoding='utf-8'))
        evidence = OPCODE_MAP.parent / metadata['evidence_file']
        self.assertEqual(metadata['mapping_file'], OPCODE_MAP.name)
        self.assertEqual(hashlib.sha256(OPCODE_MAP.read_bytes()).hexdigest(),
                         metadata['mapping_sha256'])
        self.assertEqual(hashlib.sha256(evidence.read_bytes()).hexdigest(),
                         metadata['evidence_sha256'])

if __name__=='__main__':unittest.main()
