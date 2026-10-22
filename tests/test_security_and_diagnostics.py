"""Offline negative tests; never runs a PHP input or candidate."""
from __future__ import annotations
import json,sys,unittest,random,time,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from zend_decompiler.assets import OPCODE_MAP, OPCODE_METADATA, GOLDEN, SCHEMAS, ALIGNMENT_FIXTURE, BATCH_REPORT_FIXTURE
from zend_decompiler.engine import restore_result,inspect
from zend_decompiler.batch import batch,write_candidate,atomic_bytes
from zend_decompiler.serial_parser import parse_binary,FormatError,MAX_BINARY
D=ROOT/'zend_verified_dictionary.bin';M=OPCODE_MAP;S=ROOT/'sample_inputs'

class SafetyTests(unittest.TestCase):
    def test_not_encoded(self):
        r=restore_result(S/'header_admin.php',D,M)
        self.assertEqual(r.status,'not_encoded')
        self.assertIsNone(r.code)

    def test_fail_closed_on_unknown_and_bad(self):
        # fun_all.php still fails closed.  Encoder-call fail-closed cases
        # (unresolvable symbol, arity mismatch) are covered by
        # tests/test_encoder_calls.py.
        for name in ['fun_all.php']:
            with self.subTest(name=name):
                r=restore_result(S/name,D,M)
                self.assertEqual(r.status,'unsupported')
                self.assertIsNone(r.code)
                self.assertIn('failure',r.audit)
                self.assertIn('recognition_fraction',r.audit)
        r=restore_result(ROOT/'missing_input_never_exists.php',D,M)
        self.assertEqual(r.status,'unsupported')
        self.assertIsNone(r.code)

    def test_known_unresolved_foreach_windows(self):
        # The encoder opcode position rule resolves the previously unknown
        # foreach-adjacent key 1:199 to native 98 (FETCH_DIM_TMP_VAR).  The
        # native evidence for that key stays unknown, so the confidence of the
        # disputed positions is unchanged and no window is left unmapped.
        r=restore_result(S/'fun_all.php',D,M)
        self.assertEqual((r.audit['mapped_instructions'],r.audit['serialized_instructions']),(1631,1631))
        self.assertEqual(r.audit['unknown_windows'],[])
        self.assertEqual(r.audit['confidence_counts']['unknown'],18)
        predicted=r.audit['opcode_position_rule']['predicted_positions']
        self.assertEqual([(p['group'],p['index'],p['encoded_key'],p['predicted_opcode'])
                          for p in predicted],
                         [('out_price',65,'1:199',98),('uc_rus',17,'1:199',98)])
        self.assertTrue(all(p['source']=='encoder_opcode_position_rule' for p in predicted))

    def test_atomic_write_rejects_overwrite_and_invalid_pair(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            atomic_bytes(root/'x.php',b'existing')
            with self.assertRaises(FileExistsError):atomic_bytes(root/'x.php',b'new')
            self.assertEqual((root/'x.php').read_bytes(),b'existing')
            r=restore_result(S/'basket.php',D,M)
            with self.assertRaises(FileExistsError):write_candidate(root/'x.php',root/'x.json',r)
            self.assertFalse((root/'x.json').exists())
            self.assertEqual((root/'x.php').read_bytes(),b'existing')

    def test_batch_matches_baseline_and_never_writes_failed_php(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'output'
            report=batch(S,output,D,M)
            self.assertEqual((report['total'],report['generated'],report['unsupported'],report['not_encoded']),(11,9,1,1))
            for f in ('fun_all.php',):
                self.assertFalse((output/f).exists())
                self.assertTrue((output/'_partial_READ_ONLY'/Path(f).with_suffix('.txt')).exists())
                content=(output/'_partial_READ_ONLY'/Path(f).with_suffix('.txt')).read_text()
                self.assertIn('/* UNRECOVERED */',content)
                self.assertNotIn('<?php',content)
            # A fully recovered file is written with its audit next to it.
            self.assertTrue((output/'links_fun(1).php').exists())
            self.assertTrue((output/'_audits'/'links_fun(1).json').exists())
            self.assertFalse((output/'_partial_READ_ONLY'/'links_fun.txt').exists())
            self.assertFalse((output/'header_admin.php').exists())

    def test_parser_fuzz_no_uncaught_exception_at_boundary(self):
        # Deterministic bit flips and truncations on the decoded serialization.
        # Parser exceptions are expected; uncaught exceptions are not.
        import zlib
        from zend_decompiler.serial_parser import decompress_encoded
        stream=decompress_encoded(S/'basket.php',D.read_bytes())[0][1]
        rng=random.Random(20261021)
        cases=[b'',b'\0',b'xx']+[stream[:i] for i in (0,1,2,3,8,25,50,100,len(stream)//2,len(stream)-1)]
        for _ in range(90):
            raw=bytearray(stream)
            offset=rng.randrange(len(raw))
            raw[offset]^=rng.randrange(1,256)
            cases.append(bytes(raw))
        start=time.monotonic()
        for blob in cases:
            with self.subTest(size=len(blob)):
                try:parse_binary(blob)
                except (ValueError,EOFError,UnicodeError,OverflowError,IndexError,KeyError):pass
                except Exception as exc:self.fail(f'Unexpected parser exception {type(exc).__name__}: {exc}')
        self.assertLess(time.monotonic()-start,20)
        with self.assertRaises(FormatError):parse_binary(b'X'*(MAX_BINARY+1))

if __name__=='__main__':unittest.main()
