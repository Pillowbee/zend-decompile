"""The encoder opcode position rule is a regularity, not a decoder.

The rule `native_opcode = base[encoded_byte] - (instruction index mod 8)`
reproduces the empirical opcode map exactly.  On a second protected corpus it
predicted wrongly in a noticeable share of the unseen keys, and the operand
shape guard did not catch every wrong prediction, so the rule is never used
to decode an instruction the map does not contain.
"""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from zend_decompiler.assets import (DICTIONARY, ENCODER_OPCODE_BASE, ENCODER_OPCODE_EVIDENCE,
                                    ENCODER_OPCODE_METADATA, OPCODE_MAP)
from zend_decompiler.calibrate import choose_opcode
from zend_decompiler.engine import restore_result
from zend_decompiler.opcode_position import (base_for, consistency_report, predict,
                                            rule_document, verify_against_map)

MAPPING = json.loads(OPCODE_MAP.read_text(encoding='utf-8'))


class PositionRuleDataTests(unittest.TestCase):
    def test_rule_contradicts_the_extended_empirical_map(self):
        # The rule was fitted on the first 313 keys of the map.  The map was
        # later extended with keys confirmed by a native trace, and four of
        # them contradict the rule.  That is why it is never used to decode.
        report = consistency_report(MAPPING)
        self.assertEqual(report['contradiction_count'], 4)
        self.assertEqual(sorted(item['key'] for item in report['contradictions']),
                         ['4:26', '5:7', '6:230', '7:160'])
        # Eight keys use bytes that were never observed in the first corpus.
        self.assertEqual(len(report['uncovered_keys']), 8)
        with self.assertRaises(Exception):
            verify_against_map(MAPPING)

    def test_rule_file_is_protected_by_its_own_checksums(self):
        meta = json.loads(ENCODER_OPCODE_METADATA.read_text(encoding='utf-8'))
        self.assertEqual(meta['mapping_file'], ENCODER_OPCODE_BASE.name)
        self.assertEqual(meta['mapping_sha256'],
                         hashlib.sha256(ENCODER_OPCODE_BASE.read_bytes()).hexdigest())
        evidence = ENCODER_OPCODE_BASE.with_name(meta['evidence_file'])
        self.assertEqual(meta['evidence_sha256'],
                         hashlib.sha256(evidence.read_bytes()).hexdigest())
        document = json.loads(ENCODER_OPCODE_BASE.read_text(encoding='utf-8'))
        self.assertEqual(document['mapping_sha256'],
                         hashlib.sha256(OPCODE_MAP.read_bytes()).hexdigest())

    def test_rule_is_recorded_as_measured_but_not_used(self):
        document = rule_document()
        self.assertEqual(document['status'],
                         'contradicted by the extended empirical map; research record only')
        accuracy = document['measured_accuracy']
        self.assertEqual(accuracy['status'], 'measured, not used for decoding')
        self.assertGreater(accuracy['predictions_wrong'], 0)
        self.assertGreater(accuracy['wrong_predictions_accepted_by_the_operand_shape_guard'], 0)
        self.assertEqual(accuracy['predictions_correct'] + accuracy['predictions_wrong'],
                         accuracy['predictions'])
        evidence = json.loads(ENCODER_OPCODE_EVIDENCE.read_text(encoding='utf-8'))
        self.assertEqual(evidence['measured_accuracy']['status'], accuracy['status'])


class PositionRuleIsNotADecoderTests(unittest.TestCase):
    def test_a_key_outside_the_map_stays_unmapped(self):
        # 1:199 has no entry in the empirical map and must not be decoded from
        # the position rule, because the rule predicts wrongly in some cases.
        self.assertNotIn('1:199', MAPPING['opcodes'])
        instruction = {'index': 1, 'encoded_opcode': 199, 'op1': {'type': 2, 'word0': 1, 'word1': 0},
                       'op2': {'type': 1, 'constant': {'kind': 'integer', 'value': 0}},
                       'result': {'type': 4, 'word0': 2, 'word1': 0}}
        self.assertIsNone(choose_opcode(instruction, MAPPING))
        # The rule would have predicted a number; the decoder ignores it.
        self.assertEqual(predict(instruction), 98)

    def test_the_audit_reports_no_predicted_positions(self):
        result = restore_result(ROOT / 'sample_inputs' / 'fun_all.php', DICTIONARY, OPCODE_MAP)
        self.assertEqual(result.status, 'candidate_generated', result.reason)
        rule = result.audit.get('opcode_position_rule') or {}
        self.assertEqual(rule.get('predicted_positions', []), [])

    def test_the_base_table_is_still_available_for_analysis(self):
        self.assertEqual(base_for(199), 99)
        self.assertIsNone(base_for(252))


if __name__ == '__main__':
    unittest.main()
