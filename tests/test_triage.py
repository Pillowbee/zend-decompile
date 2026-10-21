"""Triage contains structural facts but never source string literals or PHP output."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from zend_assets import OPCODE_MAP, OPCODE_METADATA, GOLDEN, SCHEMAS, ALIGNMENT_FIXTURE, BATCH_REPORT_FIXTURE
from zend_triage import triage


class ReadOnlyTriageTests(unittest.TestCase):
    def test_focus_inputs_and_prioritized_evidence_are_literal_free(self):
        report=triage([ROOT/'sample_inputs/fun_all.php',ROOT/'sample_inputs/links_fun(1).php'],
                      ROOT/'zend_verified_dictionary.bin', OPCODE_MAP)
        self.assertTrue(report['kind'].startswith('OFFLINE_LITERAL_FREE_OPCODE_AND_CFG_TRIAGE_'))
        self.assertFalse(report['semantic_equivalence_proven'])
        self.assertTrue(report['no_php_generated'])
        fun,links=report['files']
        self.assertEqual(fun['groups'],23)
        self.assertEqual(links['groups'],6)
        f_unknown=[x for x in fun['issues'] if x['kind']=='unknown_or_disputed_mapping']
        self.assertTrue(any(x['key']=='1:199' and x['group']=='out_price' for x in f_unknown))
        self.assertTrue(any(x['key']=='1:199' and x['group']=='uc_rus' for x in f_unknown))
        out_link=[x for x in fun['issues'] if x['kind']=='ambiguous_syntactic_definition'
                  and x['group']=='out_link' and x['index']==16]
        self.assertEqual(out_link[0]['reaching_definition_indices'],[13,15])
        self.assertEqual(out_link[0]['structural_paths']['status'],'complete')
        self.assertTrue(any(x['key']=='6:226' and x['index']==14 for x in links['issues']))
        for file in report['files']:
            for issue in file['issues']:
                for op in issue.get('literal_free_opcode_neighborhood',[]):
                    self.assertEqual(set(op),{'index','line','encoded_key',
                                              'native_opcode_hypothesis','evidence_status',
                                              'operand_types'})
