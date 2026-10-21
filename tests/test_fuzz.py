from __future__ import annotations
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from zend_decompiler.assets import OPCODE_MAP, OPCODE_METADATA, GOLDEN, SCHEMAS, ALIGNMENT_FIXTURE, BATCH_REPORT_FIXTURE
from zend_decompiler.fuzz import run_campaign
from zend_decompiler.serial_parser import parse_binary,decompress_encoded,FormatError

class FuzzRegressionTests(unittest.TestCase):
    def test_saved_mutations_are_rejected(self):
        manifest=json.loads((ROOT/'tests/fuzz_regressions/manifest.json').read_text())
        for row in manifest:
            with self.subTest(name=row['file']):
                b=(ROOT/'tests/fuzz_regressions'/row['file']).read_bytes()
                self.assertEqual(hashlib.sha256(b).hexdigest(),row['sha256'])
                with self.assertRaises(FormatError):parse_binary(b)

    def test_repeatable_seed_no_unexpected_parser_exception(self):
        encoded=ROOT/'sample_inputs/basket.php';dict_=ROOT/'zend_verified_dictionary.bin'
        raw=decompress_encoded(encoded,dict_.read_bytes())[0][1]
        with tempfile.TemporaryDirectory() as folder:
            a=run_campaign(raw,seed=2031,mutations=70,crash_dir=Path(folder),isolate_every=30)
            b=run_campaign(raw,seed=2031,mutations=70,crash_dir=Path(folder),isolate_every=30)
            self.assertEqual(a,b)
            self.assertEqual(a['unexpected'],0)
            self.assertEqual(a['isolation_failures'],0)
            self.assertEqual(list(Path(folder).iterdir()),[])

if __name__=='__main__':unittest.main()
