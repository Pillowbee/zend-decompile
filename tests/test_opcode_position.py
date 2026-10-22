"""Encoder opcode position rule: consistency, predictions and refusals.

The rule predicts a native opcode for positions the empirical map does not
contain.  It must never contradict the empirical map, never override a map
entry, and never predict an opcode whose PHP 5.2 handler does not accept the
observed operand shape.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from zend_decompiler.assets import (DICTIONARY, ENCODER_OPCODE_BASE, ENCODER_OPCODE_EVIDENCE,
                                    OPCODE_MAP)
from zend_decompiler.calibrate import choose_opcode
from zend_decompiler.engine import restore_result
from zend_decompiler.opcode_position import (PositionRuleError, base_for, evidence_document,
                                             opcode_for, predict, rule_document,
                                             shape_compatible, verify_against_map)
from zend_decompiler.serial_parser import decompress_encoded, parse_binary

MAPPING = json.loads(OPCODE_MAP.read_text(encoding='utf-8'))


def op(index: int, byte: int, op1_type: int = 2, op2_type: int = 1,
       result_type: int = 4) -> dict:
    node = lambda t: {'type': t, 'word0': 0, 'word1': 0}
    return {'index': index, 'encoded_opcode': byte, 'op1': node(op1_type),
            'op2': node(op2_type), 'result': node(result_type), 'extended_value': 0}


class PositionRuleConsistencyTests(unittest.TestCase):
    def test_rule_reproduces_every_key_of_the_empirical_map(self):
        summary = verify_against_map(MAPPING)
        self.assertEqual(summary['contradictions'], 0)
        self.assertEqual(summary['checked_keys'], len(MAPPING['opcodes']))
        self.assertEqual(summary['uncovered_keys'], [])
        for key, mapped in MAPPING['opcodes'].items():
            position, byte = key.split(':')
            with self.subTest(key=key):
                self.assertEqual(base_for(int(byte)) - int(position), mapped)

    def test_rule_matches_the_archived_handler_trace_audit(self):
        document = evidence_document()
        cross = document['independent_cross_check']
        self.assertEqual(cross['contradictions'], [])
        self.assertGreater(cross['single_candidate_keys_matched'], 250)
        for entry in cross['multi_candidate_keys']:
            self.assertTrue(entry['predicted_in_candidates'], entry)
        # The key without any archived candidate is the one the rule predicts.
        without = [e['key'] for e in cross['keys_without_archived_candidate']]
        self.assertEqual(without, ['1:199'])

    def test_map_entries_are_never_overridden(self):
        mapping = {'opcodes': {'1:199': 77}, 'names': MAPPING['names'],
                   'conditional_send_keys': []}
        # The map entry wins even where the rule would predict something else.
        self.assertEqual(choose_opcode(op(1, 199), mapping), 77)

    def test_contradiction_with_the_map_is_refused(self):
        broken = {'opcodes': dict(MAPPING['opcodes']), 'names': MAPPING['names']}
        broken['opcodes']['0:13'] = broken['opcodes']['0:13'] + 1
        with self.assertRaises(PositionRuleError):
            verify_against_map(broken)

    def test_rule_document_is_protected_by_its_own_checksums(self):
        meta = json.loads((ENCODER_OPCODE_BASE.with_name(
            ENCODER_OPCODE_BASE.name + '.meta.json')).read_text(encoding='utf-8'))
        import hashlib
        self.assertEqual(meta['mapping_sha256'],
                         hashlib.sha256(ENCODER_OPCODE_BASE.read_bytes()).hexdigest())
        evidence = ENCODER_OPCODE_BASE.with_name(meta['evidence_file'])
        self.assertEqual(meta['evidence_sha256'],
                         hashlib.sha256(evidence.read_bytes()).hexdigest())
        self.assertEqual(meta['status'], 'inferred')


class PositionRulePredictionTests(unittest.TestCase):
    def test_unknown_foreach_key_is_predicted_as_fetch_dim_tmp_var(self):
        # 1:199 -> base 99 - position 1 = 98 = ZEND_FETCH_DIM_TMP_VAR.
        self.assertEqual(base_for(199), 99)
        predicted = op(1, 199)
        self.assertEqual(predict(predicted), 98)
        self.assertEqual(opcode_for(predicted), 98)
        self.assertTrue(shape_compatible(predicted, 98))

    def test_prediction_is_refused_when_the_operand_shape_does_not_fit(self):
        # FETCH_DIM_TMP_VAR accepts CONST|TMP for op1 and CONST for op2.
        self.assertFalse(shape_compatible(op(1, 199, op1_type=16), 98))
        self.assertFalse(shape_compatible(op(1, 199, op2_type=2), 98))
        self.assertIsNone(opcode_for(op(1, 199, op1_type=16)))
        self.assertIsNone(opcode_for(op(1, 199, op2_type=2)))

    def test_unknown_byte_is_not_predicted(self):
        self.assertIsNone(base_for(252))
        self.assertIsNone(opcode_for(op(3, 2)))

    def test_negative_prediction_is_refused(self):
        # Base 2 at position 7 would give a negative opcode number.
        self.assertEqual(base_for(19), 2)
        self.assertIsNone(predict(op(7, 19)))
        self.assertIsNone(opcode_for(op(7, 19)))

    def test_prediction_without_handler_signature_is_refused(self):
        # Opcode 137 has no handler in the saved PHP 5.2 header.
        self.assertFalse(shape_compatible(op(0, 250), 137))


class PositionRuleInTheDecoderTests(unittest.TestCase):
    def test_audit_reports_the_predicted_positions(self):
        result = restore_result(ROOT / 'sample_inputs' / 'fun_all.php', DICTIONARY, OPCODE_MAP)
        rule = result.audit['opcode_position_rule']
        self.assertEqual(rule['status'], 'inferred')
        self.assertEqual([(p['group'], p['index'], p['encoded_key'], p['predicted_opcode'])
                          for p in rule['predicted_positions']],
                         [('out_price', 65, '1:199', 98), ('uc_rus', 17, '1:199', 98)])
        self.assertEqual(result.audit['mapped_instructions'],
                         result.audit['serialized_instructions'])

    def test_native_evidence_for_the_predicted_key_stays_unknown(self):
        evidence = json.loads(
            (OPCODE_MAP.with_name('opcode_evidence.json')).read_text(encoding='utf-8'))
        self.assertEqual(evidence['entries']['1:199']['status'], 'unknown')
        self.assertIsNone(evidence['entries']['1:199']['opcode'])
        result = restore_result(ROOT / 'sample_inputs' / 'fun_all.php', DICTIONARY, OPCODE_MAP)
        self.assertEqual(result.audit['confidence_counts']['confirmed'], 0)

    def test_position_rule_does_not_change_the_known_keys(self):
        streams = decompress_encoded(ROOT / 'sample_inputs' / 'fun_all.php',
                                     DICTIONARY.read_bytes())
        parsed = parse_binary(streams[0][1])
        for group in [parsed['main']] + list(parsed['functions']):
            for instruction in group['opcodes']:
                key = f"{instruction['index'] % 8}:{instruction['encoded_opcode']}"
                if key not in MAPPING['opcodes']:
                    continue
                with self.subTest(key=key):
                    self.assertEqual(choose_opcode(instruction, MAPPING),
                                     MAPPING['opcodes'][key])


if __name__ == '__main__':
    unittest.main()
