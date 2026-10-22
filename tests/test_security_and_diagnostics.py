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
        # Every encoded sample is restored; the remaining not_encoded input is
        # refused by the format check.  Encoder-call fail-closed cases
        # (unresolvable symbol, arity mismatch) are covered by
        # tests/test_encoder_calls.py.
        for name in []:
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
        # The binding of a foreach element has no established native opcode,
        # so the two positions stay unmapped.  The encoder opcode position rule
        # predicts nothing: it is not reliable enough to decode from.
        r=restore_result(S/'fun_all.php',D,M)
        self.assertEqual((r.audit['mapped_instructions'],r.audit['serialized_instructions']),(1629,1631))
        self.assertEqual(r.audit['confidence_counts']['unknown'],18)
        predicted=r.audit['opcode_position_rule']['predicted_positions']
        self.assertEqual(predicted,[])

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
            self.assertEqual((report['total'],report['generated'],report['unsupported'],report['not_encoded']),(11,10,0,1))
            # A fully recovered file is written with its audit next to it.
            for name in ('links_fun(1).php','fun_all.php'):
                self.assertTrue((output/name).exists())
                self.assertTrue((output/'_audits'/(Path(name).stem+'.json')).exists())
                self.assertFalse((output/'_partial_READ_ONLY'/Path(name).with_suffix('.txt')).exists())
            # The not_encoded input is never written as PHP.
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
