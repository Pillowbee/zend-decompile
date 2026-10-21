"""Compare the current public restoration engine against immutable goldens.

Never execute any encoded input or generated PHP as part of the test suite.
"""
from __future__ import annotations
import hashlib, json, re, sys, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zend_decompiler.assets import GOLDEN, OPCODE_MAP, DICTIONARY
from zend_decompiler.engine import restore_result


def neutralize_generator_comment(code: bytes) -> bytes:
    # The generator's current release is allowed to change, but no PHP is.
    return re.sub(rb'EXPERIMENTAL Zend recovery v\d+\.',
                  b'EXPERIMENTAL Zend recovery VERSION.', code, count=1)


class GoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads((GOLDEN/'manifest.json').read_text())

    def test_original_input_data_unchanged(self):
        for name, expected in self.manifest['inputs'].items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((ROOT/'sample_inputs'/name).read_bytes()).hexdigest(),expected)
        self.assertEqual(hashlib.sha256(DICTIONARY.read_bytes()).hexdigest(),self.manifest['dictionary_sha256'])
        self.assertEqual(hashlib.sha256(OPCODE_MAP.read_bytes()).hexdigest(),self.manifest['mapping_sha256'])

    def test_current_engine_matches_golden_php_bytes(self):
        for name in self.manifest['full_candidates']:
            with self.subTest(name=name):
                result=restore_result(ROOT/'sample_inputs'/name,DICTIONARY,OPCODE_MAP)
                self.assertEqual(result.status,'candidate_generated', result.reason)
                self.assertEqual(neutralize_generator_comment(result.code),
                                 neutralize_generator_comment((GOLDEN/'code'/name).read_bytes()))

    def test_current_engine_preserves_golden_group_audits(self):
        for name in self.manifest['full_candidates']:
            with self.subTest(name=name):
                result=restore_result(ROOT/'sample_inputs'/name,DICTIONARY,OPCODE_MAP)
                original=json.loads((GOLDEN/'audit'/(name+'.json')).read_text())
                self.assertEqual(result.status,'candidate_generated')
                self.assertEqual(result.audit['total_serialized_instructions'],original['total_serialized_instructions'])
                self.assertEqual(len(result.audit['groups']),len(original['groups']))
                for expected, current in zip(original['groups'], result.audit['groups']):
                    # Version-independent comparison still checks EVERY archived
                    # group field. The current decoder adds its rule counters.
                    observed={key:current.get(key) for key in expected}
                    # JSON serializes tuple CFG edges as JSON arrays.
                    self.assertEqual(json.loads(json.dumps(observed)),expected)

if __name__=='__main__':unittest.main()
