"""Read-only call-site hypotheses: real immutable corpus + synthetic mutations.

No fabricated encoded PHP streams, no PHP execution, no changes to the
production decoder, native opcode map, or golden candidates.
"""
from __future__ import annotations

import copy
import json
import unittest
from collections import Counter

from zend_decompiler.assets import DICTIONARY, OPCODE_MAP, BASE
from zend_decompiler.header_call_hypothesis import (
    DISPUTED_KEYS, analyze_file, analyze_parsed,
)
from zend_decompiler.readonly_dataflow import _validated_evidence
from zend_decompiler.serial_parser import decompress_encoded, parse_binary


class HeaderIndexedCallEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapping = json.loads(OPCODE_MAP.read_text(encoding='utf-8'))
        cls.evidence = _validated_evidence(OPCODE_MAP)
        cls.parsed = {}
        for name in ('links_fun(1).php', 'fun_all.php'):
            source = BASE / 'sample_inputs' / name
            cls.parsed[name] = parse_binary(decompress_encoded(
                source, DICTIONARY.read_bytes())[0][1])

    def report(self, name: str, parsed=None, mapping=None, evidence=None):
        return analyze_parsed(
            self.parsed[name] if parsed is None else parsed,
            self.mapping if mapping is None else mapping,
            self.evidence if evidence is None else evidence,
        )

    @staticmethod
    def observation(report, group: str, index: int) -> dict:
        matching = [r for r in report['observations']
                    if r['group'] == group and r['index'] == index]
        if len(matching) != 1:
            raise AssertionError(f'Expected one observation for {group}#{index}: {matching}')
        return matching[0]

    @staticmethod
    def op(parsed: dict, group: str, index: int) -> dict:
        if group == '<main>':
            return parsed['main']['opcodes'][index]
        matches = [f for f in parsed['functions']
                   if bytes.fromhex(f['name_hex']).decode('ascii') == group]
        if len(matches) != 1:
            raise AssertionError('Expected unique group')
        return matches[0]['opcodes'][index]

    def assert_rejected(self, parsed, expected: str, *, name='links_fun(1).php',
                        group='<main>', index=14):
        report = self.report(name, parsed)
        row = self.observation(report, group, index)
        self.assertEqual(row['status'], 'rejected', row)
        self.assertEqual(row['reason'], expected, row)

    def test_all_18_real_observations_have_explicit_uncertainty(self):
        links = self.report('links_fun(1).php')
        full = self.report('fun_all.php')
        self.assertEqual(len(links['observations']), 2)
        self.assertEqual(len(full['observations']), 16)
        both = links['observations'] + full['observations']
        self.assertEqual(Counter(r['status'] for r in both),
                         {'experimental_structural_match': 15, 'unverifiable_cfg': 3})
        self.assertTrue(all(r['encoded_key'] in DISPUTED_KEYS for r in both))
        self.assertTrue(all(r['evidence_status'] == 'unknown' for r in both))
        for report in (links, full):
            self.assertFalse(report['php_generated'])
            self.assertFalse(report['semantic_equivalence_proven'])
            self.assertFalse(report['disputed_opcode_promoted'])
            self.assertFalse(report['map_rewritten'])
            self.assertIn('assumes', report['cfg_note'])
        self.assertEqual({(r['group'], r['index'], r['callee'])
                          for r in links['observations']},
                         {('<main>', 14, 'send_mail'),
                          ('count_ln_out', 3, 'count_ln')})
        expected = {
            ('out_price', 21, 'currency_type'),
            ('out_price', 106, 'currency_type'),
            ('out_price', 115, 'currency_type'),
            ('path_groups', 26, 'out_link'),
            ('path_groups', 122, 'out_link'),
            ('page_links_out', 260, 'out_link'),
            ('page_links_out', 287, 'out_link'),
            ('page_links_out', 312, 'out_link'),
            ('mail_hide', 17, 'url_prefix'),
            ('mail_hide', 30, 'url_prefix'),
            ('mail_hide', 41, 'url_prefix'),
            ('out_replace_teg', 71, 'url_prefix'),
            ('out_replace_files', 32, 'out_replace_teg'),
            ('minmax_price', 48, 'out_price'),
            ('minmax_price', 62, 'out_price'),
            ('minmax_price', 74, 'out_price'),
        }
        self.assertEqual({(r['group'], r['index'], r['callee'])
                          for r in full['observations']}, expected)

    def test_cfg_unmodelled_foreach_is_not_reported_as_valid(self):
        rows = [x for x in self.report('fun_all.php')['observations']
                if x['group'] == 'out_price']
        self.assertEqual([r['index'] for r in rows], [21, 106, 115])
        self.assertTrue(all(r['status'] == 'unverifiable_cfg' for r in rows))
        self.assertTrue(all(r['basic_block'] is None for r in rows))

    def test_offline_api_matches_pure_function_without_rewriting_parsed(self):
        p = copy.deepcopy(self.parsed['links_fun(1).php'])
        before = copy.deepcopy(p)
        a = self.report('links_fun(1).php', p)
        self.assertEqual(p, before)
        b = analyze_file(BASE / 'sample_inputs' / 'links_fun(1).php')
        self.assertEqual(b['observations'], a['observations'])
        self.assertEqual(b['file'], 'links_fun(1).php')

    def test_wrong_status_or_opcode_evidence_is_rejected(self):
        for change in ({'status': 'confirmed'}, {'opcode': 60}):
            ev = copy.deepcopy(self.evidence)
            ev['6:226'].update(change)
            row = self.observation(self.report('links_fun(1).php', evidence=ev), '<main>', 14)
            self.assertEqual((row['status'], row['reason']),
                             ('rejected', 'not_unconfirmed_140_evidence'))

    def test_symbol_index_out_of_bounds(self):
        p = copy.deepcopy(self.parsed['links_fun(1).php'])
        self.op(p, '<main>', 14)['op1']['word0'] = len(p['header_symbols'])
        self.assert_rejected(p, 'symbol_index_out_of_bounds')

    def test_negative_symbol_index_is_rejected(self):
        p = copy.deepcopy(self.parsed['links_fun(1).php'])
        self.op(p, '<main>', 14)['op1']['word0'] = -1
        self.assert_rejected(p, 'symbol_index_out_of_bounds')

    def test_invalid_symbol_name(self):
        p = copy.deepcopy(self.parsed['links_fun(1).php'])
        p['header_symbols'][1]['name_hex'] = b'not a php name'.hex()
        self.assert_rejected(p, 'invalid_identifier')

    def test_symbol_table_index_mismatch(self):
        p = copy.deepcopy(self.parsed['links_fun(1).php'])
        p['header_symbols'][1]['index'] = 100
        self.assert_rejected(p, 'symbol_table_index_mismatch')

    def test_invalid_symbol_hex(self):
        p = copy.deepcopy(self.parsed['links_fun(1).php'])
        p['header_symbols'][1]['name_hex'] = 'not-hex'
        self.assert_rejected(p, 'invalid_symbol_encoding')

    def test_nonexistent_callee(self):
        p = copy.deepcopy(self.parsed['links_fun(1).php'])
        p['header_symbols'][1]['name_hex'] = b'other_func'.hex()
        self.assert_rejected(p, 'callee_not_uniquely_defined_locally')

    def test_duplicate_local_callee(self):
        p = copy.deepcopy(self.parsed['links_fun(1).php'])
        function = next(f for f in p['functions'] if bytes.fromhex(f['name_hex']) == b'send_mail')
        p['functions'].append(copy.deepcopy(function))
        self.assert_rejected(p, 'callee_not_uniquely_defined_locally')

    def test_wrong_argument_count(self):
        p = copy.deepcopy(self.parsed['links_fun(1).php'])
        self.op(p, '<main>', 14)['extended_value'] = 1
        self.assert_rejected(p, 'arity_signature_mismatch')

    def test_wrong_recv_parameter_number(self):
        p = copy.deepcopy(self.parsed['links_fun(1).php'])
        self.op(p, 'send_mail', 1)['op1']['constant']['value'] = 9
        self.assert_rejected(p, 'unverifiable_signature')

    def test_wrong_operand_type_or_marker(self):
        for field, key, bad in [('op1', 'type', 1), ('op1', 'word1', 0),
                                ('op2', 'word1', 0), ('result', 'type', 8)]:
            with self.subTest(field=field, key=key):
                p = copy.deepcopy(self.parsed['links_fun(1).php'])
                self.op(p, '<main>', 14)[field][key] = bad
                self.assert_rejected(p, 'operand_shape_mismatch')

    def test_wrong_send_order_or_marker(self):
        for field, key, bad in [('op2', 'word0', 2), ('op2', 'word1', 0),
                                ('result', 'type', 4)]:
            with self.subTest(field=field, key=key):
                p = copy.deepcopy(self.parsed['links_fun(1).php'])
                self.op(p, '<main>', 12)[field][key] = bad
                reason = 'send_result_mismatch' if field == 'result' else 'send_position_or_marker_mismatch'
                self.assert_rejected(p, reason)

    def test_wrong_send_target(self):
        p = copy.deepcopy(self.parsed['links_fun(1).php'])
        self.op(p, '<main>', 12)['extended_value'] = 61
        self.assert_rejected(p, 'send_target_mismatch')

    def test_non_send_in_run(self):
        p = copy.deepcopy(self.parsed['links_fun(1).php'])
        # 4:10 is IS_SMALLER (19), a known non-SEND instruction.
        self.op(p, '<main>', 12)['encoded_opcode'] = 10
        self.assert_rejected(p, 'non_send_in_argument_run')

    def test_wrong_send_operand_type(self):
        p = copy.deepcopy(self.parsed['links_fun(1).php'])
        self.op(p, '<main>', 12)['op1']['type'] = 1
        self.assert_rejected(p, 'send_var_shape_mismatch')

    def test_cfg_jump_target_enters_argument_run(self):
        p = copy.deepcopy(self.parsed['links_fun(1).php'])
        self.op(p, '<main>', 11)['op2']['word0'] = 13
        self.assert_rejected(p, 'send_crosses_basic_block')

    def test_initialized_call_not_closed_before_direct_sends(self):
        # A branch at #11 starts the #12 block, so use count_ln_out,
        # whose first block contains its initial RECV and the target.
        p2 = copy.deepcopy(self.parsed['links_fun(1).php'])
        self.op(p2, 'count_ln_out', 0)['encoded_opcode'] = 107
        self.assert_rejected(p2, 'unfinished_initialized_call', group='count_ln_out', index=3)

    def test_unclosed_prior_send_is_rejected(self):
        p = copy.deepcopy(self.parsed['links_fun(1).php'])
        # 0:205 -> SEND_VAL (65), added synthetically before existing SENDs.
        prior = self.op(p, 'count_ln_out', 0)
        prior['encoded_opcode'] = 205
        prior['op1'] = {'type': 1, 'constant': {'kind': 'integer', 'value': 7}}
        prior['op2'] = {'type': 8, 'word0': 1, 'word1': 1}
        prior['result'] = {'type': 8, 'word0': 0, 'word1': 1}
        prior['extended_value'] = 60
        self.assert_rejected(p, 'unclosed_prior_send', group='count_ln_out', index=3)

    def test_zero_argument_call_with_prior_send_rejected(self):
        p = copy.deepcopy(self.parsed['fun_all.php'])
        # The url_prefix call at mail_hide#17 normally takes zero arguments.
        # Make the preceding known non-SEND #16 into a SEND opcode 0:205.
        prior = self.op(p, 'mail_hide', 16)
        prior['encoded_opcode'] = 205
        row = self.observation(self.report('fun_all.php', p), 'mail_hide', 17)
        self.assertEqual((row['status'], row['reason']),
                         ('rejected', 'unclosed_prior_send'))

    def test_unmodeled_cfg_is_refused_without_guessing(self):
        report = self.report('fun_all.php')
        self.assertEqual(Counter(r['reason'] for r in report['observations']
                                 if r['status'] == 'unverifiable_cfg'),
                         {'other_unknown_opcodes': 3})


if __name__ == '__main__':
    unittest.main()
