from __future__ import annotations
import hashlib,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from zend_decompiler.assets import OPCODE_MAP, OPCODE_METADATA, GOLDEN, SCHEMAS, ALIGNMENT_FIXTURE, BATCH_REPORT_FIXTURE
from zend_decompiler.engine import restore_result
from zend_decompiler.parser_isolated import parse_isolated
from zend_decompiler.serial_parser import decompress_encoded,MAX_BINARY
D=ROOT/'zend_verified_dictionary.bin';M=OPCODE_MAP

class Diagnostics23(unittest.TestCase):
    def test_real_decoder_rules_not_opcodes_encountered(self):
        result=restore_result(ROOT/'sample_inputs/import(1).php',D,M)
        self.assertEqual(result.status,'candidate_generated')
        self.assertEqual(result.audit['rule_usage']['BOOL_NOT'],1)
        self.assertTrue(result.audit['supported_unary_bool_not'])
        self.assertFalse(result.audit['supported_simple_at_function_call'])
        self.assertEqual(sum(g['decoder_rule_usage'].get('BOOL_NOT',0) for g in result.audit['groups']),1)
        user=restore_result(ROOT/'sample_inputs/user.php',D,M)
        self.assertFalse(user.audit['supported_unary_bool_not'])
        self.assertEqual(user.audit['rule_usage'].get('BOOL_NOT',0),0)

    def test_exact_failure_instruction_and_opcode_window(self):
        expectations={'fun_all.php':('out_link',16,16)}
        for file,(group,index,block_start) in expectations.items():
            with self.subTest(file=file):
                result=restore_result(ROOT/'sample_inputs'/file,D,M)
                self.assertEqual(result.status,'unsupported')
                self.assertIsNone(result.code)
                failure=result.audit['failure']
                self.assertEqual(failure['opcode_index'],index)
                self.assertEqual(failure['index_precision'],'exact_decoder_instruction_on_exception')
                self.assertEqual(failure['block_start_opcode_index'],block_start)
                self.assertEqual(failure['block_window']['group'],group)
                self.assertEqual(failure['block_window']['index'],index)
        # The disputed native keys stay 'unknown' in the native map even where
        # the Encoder-level call form is recognised and restored.
        r=restore_result(ROOT/'sample_inputs/links_fun(1).php',D,M)
        self.assertEqual(r.status,'candidate_generated')
        self.assertEqual(r.audit['confidence_counts']['unknown'],2)
        self.assertEqual(r.audit['confidence_counts']['confirmed'],0)
        self.assertEqual(r.audit['rule_usage']['ENCODER_CALL'],2)
        self.assertEqual(r.audit['mapping_sha256'],
                         hashlib.sha256(OPCODE_MAP.read_bytes()).hexdigest())

    def test_source_confidence_never_promoted_without_evidence(self):
        r=restore_result(ROOT/'sample_inputs/fun_all.php',D,M)
        self.assertEqual(r.audit['confidence_counts']['confirmed'],0)
        self.assertEqual(r.audit['mapped_instructions'],1631)
        self.assertEqual(r.audit['serialized_instructions'],1631)
        self.assertEqual(r.audit['mapping_metadata_sha256'],hashlib.sha256(OPCODE_METADATA.read_bytes()).hexdigest())
        self.assertTrue(all(g['confirmed_instruction_count']==0 for g in r.audit['group_diagnostics']))
        self.assertTrue(all(g['confirmed_fraction']==0 for g in r.audit['group_diagnostics'] if g['instructions']))
        self.assertEqual(r.audit['round_trip']['status'],'not_run')

    def test_integrity_metadata_fail_closed(self):
        meta_path=OPCODE_METADATA
        original=meta_path.read_bytes()
        try:
            bad=json.loads(original);bad['mapping_sha256']='0'*64
            meta_path.write_text(json.dumps(bad))
            result=restore_result(ROOT/'sample_inputs/basket.php',D,M)
            self.assertEqual(result.status,'unsupported')
            self.assertIsNone(result.code)
            self.assertIn('SHA256',result.reason)
        finally:
            meta_path.write_bytes(original)

    def test_parse_recursion_and_memory_errors_are_structured(self):
        for exc in (RecursionError('forced'),MemoryError('forced')):
            with self.subTest(exc=type(exc).__name__):
                with patch('zend_decompiler.engine.parse_binary',side_effect=exc):
                    result=restore_result(ROOT/'sample_inputs/basket.php',D,M)
                    self.assertEqual(result.status,'unsupported')
                    self.assertIsNone(result.code)
                    self.assertEqual(result.audit['failure']['type'],type(exc).__name__)

    def test_bounded_isolated_parser(self):
        raw=decompress_encoded(ROOT/'sample_inputs/basket.php',D.read_bytes())[0][1]
        self.assertEqual(parse_isolated(raw)['status'],'parsed')
        for blob in (b'',b'\0',raw[:25],raw[:len(raw)//2]):
            self.assertEqual(parse_isolated(blob)['status'],'unsupported')
        with self.assertRaises(ValueError):parse_isolated(raw,max_memory_mb=32)
        self.assertEqual(parse_isolated(b'Z'*(MAX_BINARY+1))['status'],'unsupported')

if __name__=='__main__':unittest.main()
