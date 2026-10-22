"""Stable JSON data layout, independent of release number and research snapshots."""
import hashlib
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zend_decompiler.assets import (OPCODE_MAP, OPCODE_METADATA, ALIGNMENT_FIXTURE,
                                    ENCODER_CALL_MAP, ENCODER_CALL_EVIDENCE,
                                    ENCODER_CALL_METADATA)

class DataLayoutTests(unittest.TestCase):
    def test_no_root_level_json_or_legacy_duplicate_map(self):
        self.assertEqual(list(ROOT.glob('*.json')), [])
        self.assertEqual(sorted(p.name for p in (ROOT/'data/opcodes').glob('*.json')),
                         ['encoder_call_evidence.json', 'encoder_call_map.json',
                          'encoder_call_map.json.meta.json', 'opcode_evidence.json',
                          'opcode_map.json', 'opcode_map.json.meta.json'])
    def test_encoder_call_map_and_evidence_integrity(self):
        meta=json.loads(ENCODER_CALL_METADATA.read_text(encoding='utf-8'))
        self.assertEqual(meta['mapping_file'], ENCODER_CALL_MAP.name)
        self.assertEqual(meta['evidence_file'], 'encoder_call_evidence.json')
        self.assertEqual(meta['status'], 'inferred')
        self.assertEqual(meta['mapping_sha256'],
                         hashlib.sha256(ENCODER_CALL_MAP.read_bytes()).hexdigest())
        evidence=ENCODER_CALL_MAP.with_name(meta['evidence_file'])
        self.assertEqual(meta['evidence_sha256'], hashlib.sha256(evidence.read_bytes()).hexdigest())
        document=json.loads(evidence.read_text(encoding='utf-8'))
        self.assertEqual(document['mapping_sha256'], meta['mapping_sha256'])
        self.assertEqual(document['summary']['call_sites'], 18)
        self.assertEqual(document['summary']['argc_matches_recv'], 18)
        self.assertTrue(all(entry['status']=='inferred' for entry in document['entries'].values()))
        self.assertTrue(all(entry['cross_validated'] for entry in document['entries'].values()))
    def test_native_opcode_map_is_not_rewritten_by_encoder_calls(self):
        # The Encoder-level call table lives beside the native map and must not
        # change it: the native number of these positions stays unresolved.
        meta=json.loads(OPCODE_METADATA.read_text(encoding='utf-8'))
        self.assertEqual(meta['mapping_sha256'],
                         hashlib.sha256(OPCODE_MAP.read_bytes()).hexdigest())
        mapping=json.loads(OPCODE_MAP.read_text(encoding='utf-8'))
        for key in json.loads(ENCODER_CALL_MAP.read_text(encoding='utf-8'))['raw_keys']:
            self.assertEqual(mapping['opcodes'][key], 140)
            self.assertNotIn(str(140), mapping['names'])
    def test_opcode_map_and_evidence_integrity(self):
        meta=json.loads(OPCODE_METADATA.read_text(encoding='utf-8'))
        self.assertEqual(meta['mapping_file'], OPCODE_MAP.name)
        self.assertEqual(meta['evidence_file'], 'opcode_evidence.json')
        self.assertNotIn('hypotheses_file', meta)
        self.assertEqual({issue['identifier'] for issue in meta['hypotheses']['issues']},
                         {'140','1:199','49'})
        self.assertEqual(meta['mapping_sha256'], hashlib.sha256(OPCODE_MAP.read_bytes()).hexdigest())
        evidence=OPCODE_MAP.with_name(meta['evidence_file'])
        self.assertEqual(meta['evidence_sha256'],hashlib.sha256(evidence.read_bytes()).hexdigest())
        self.assertEqual(json.loads(evidence.read_text())['mapping_sha256'], meta['mapping_sha256'])
    def test_preserved_archived_alignment_fixture(self):
        self.assertTrue(ALIGNMENT_FIXTURE.is_file())
        r=json.loads(ALIGNMENT_FIXTURE.read_text(encoding='utf-8'))
        self.assertEqual(r['serialized_instructions'], 4204)
    def test_merged_snapshots_are_structurally_intact(self):
        names={'analysis':{'source_anchored_ir','triage','readonly_dataflow_fun','readonly_dataflow_links','own_foreach_compile_check'},
               'header_audits':{'php52_family','incompatible_headers','comparison_summary'}}
        for group, keys in names.items():
            with self.subTest(group=group):
                archive=json.loads((ROOT/'data/research'/(group+'.json')).read_text(encoding='utf-8'))
                self.assertEqual(archive['schema_version'],1)
                self.assertEqual(set(archive['records']), keys)
                self.assertEqual(set(archive['source_integrity']), keys)
                for key, obj in archive['records'].items():
                    b=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
                    self.assertEqual(hashlib.sha256(b).hexdigest(),archive['source_integrity'][key]['payload_sha256'])
                    self.assertRegex(archive['source_integrity'][key]['original_sha256'],r'^[0-9a-f]{64}$')
