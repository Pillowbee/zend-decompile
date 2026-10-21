"""Only OWN fixtures are compiled; protected PHP is never run or compiled here."""
from __future__ import annotations
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from zend_decompiler.assets import OPCODE_MAP, OPCODE_METADATA, GOLDEN, SCHEMAS, ALIGNMENT_FIXTURE, BATCH_REPORT_FIXTURE
from zend_decompiler.compiler_oracle import (read_probe_log,ProbeFormatError,compile_own_fixture,
                                  corpus_metrics,generate_fixture_manifest)

class OwnOracleTests(unittest.TestCase):
    def test_normalized_fixtures_exact(self):
        src=ROOT/'corpus/own_sources'; dumps=ROOT/'corpus/compile_only_dumps'
        m=generate_fixture_manifest(src,dumps)
        self.assertEqual(len(m['programs']),5)
        self.assertEqual(sum(p['function_count'] for p in m['programs']),5)
        for p in m['programs']:
            name=Path(p['name']).stem
            got=read_probe_log((dumps/(name+'.log')).read_text(encoding='utf-8'))
            saved=json.loads((dumps/(name+'.normalized.json')).read_text(encoding='utf-8'))
            self.assertEqual(got,saved)
            self.assertEqual(hashlib.sha256((src/p['name']).read_bytes()).hexdigest(),p['sha256'])

    def test_do_not_invent_round_trip_success(self):
        manifest=json.loads((ROOT/'corpus/manifest.json').read_text())
        metrics=corpus_metrics(manifest)
        self.assertEqual(metrics['compile_only_files'],5)
        self.assertEqual(metrics['compile_only_functions'],5)
        self.assertIsNone(metrics['restoration_success_fraction_files'])
        self.assertIsNone(metrics['restoration_success_fraction_functions'])
        self.assertEqual(metrics['round_trip']['status'],'not_run')
        self.assertEqual(metrics,json.loads((ROOT/'corpus/metrics.json').read_text()))

    def test_reject_invalid_probe_traces(self):
        for text in ('','[probe] #00 opcode=49 handler=0x0 line=1 extended=1\nNo syntax errors detected',
                     '[probe] function_name=<main>\n[probe] op_array=x\n[probe] #12 opcode=49 handler=0x0 line=1 extended=0\nNo syntax errors detected'):
            with self.subTest(text=text[:20]),self.assertRaises(ProbeFormatError):read_probe_log(text)

    def test_probe_does_not_compile_protected_file(self):
        with self.assertRaises(ValueError):
            compile_own_fixture(ROOT/'sample_inputs/basket.php',ROOT/'corpus/own_sources',
                                ROOT/'php52_linter',Path('/mnt/data/zend_work/probe_with_cv.so'))

    def test_recompile_own_fixtures_if_probe_available(self):
        binary=ROOT/'php52_linter';probe=Path('/mnt/data/zend_work/probe_with_cv.so');libs=Path('/mnt/data/php52_libs')
        if not (binary.exists() and probe.exists() and libs.exists()):
            self.skipTest('Local diagnostic PHP 5.2 compile-only probe is not available')
        for f in sorted((ROOT/'corpus/own_sources').glob('*.php')):
            with self.subTest(file=f.name):
                outcome=compile_own_fixture(f,ROOT/'corpus/own_sources',binary,probe,library_dir=libs)
                expected=json.loads((ROOT/'corpus/compile_only_dumps'/(f.stem+'.normalized.json')).read_text())
                self.assertEqual(outcome['groups'],expected['groups'])
                self.assertEqual(outcome['total_instructions'],expected['total_instructions'])

if __name__=='__main__':unittest.main()
