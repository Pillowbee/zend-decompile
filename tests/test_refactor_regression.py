"""Monotonic coverage proof against the original block decoder.

The reference stores hashes of *previously successful* blocks, captured from
untouched Git commit 5e03d01. New recoveries may add blocks, but old successes
must remain identical. Never execute input PHP.
"""
from __future__ import annotations
import hashlib, json, re, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from zend_decompiler.assets import OPCODE_MAP, DICTIONARY
from zend_decompiler.block_previews import run

REFERENCE=json.loads((ROOT/'tests/fixtures/preview_completed_blocks.json').read_text(encoding='utf8'))

def block_fingerprint(block):
    summary={key:block[key] for key in ('status','statements','branch')}
    return hashlib.sha256(json.dumps(summary,sort_keys=True,ensure_ascii=False,
                       separators=(',',':')).encode('utf8')).hexdigest()

class RefactorRegression(unittest.TestCase):
    def test_completed_block_diagnostics_are_preserved_or_extended(self):
        inputs=sorted((ROOT/'sample_inputs').glob('*.php'))
        self.assertEqual({f.name for f in inputs},set(REFERENCE))
        improvement=0
        for source in inputs:
            with self.subTest(source=source.name):
                old=REFERENCE[source.name]
                if old['status']=='error':
                    with self.assertRaisesRegex(Exception,re.escape(old['message'])):
                        run(source,DICTIONARY,OPCODE_MAP)
                    continue
                current=run(source,DICTIONARY,OPCODE_MAP)
                self.assertEqual(current['total'],old['total'])
                self.assertEqual(len(current['blocks']),old['blocks'])
                self.assertGreaterEqual(current['local_blocks'],old['local_blocks'])
                self.assertGreaterEqual(current['local_instructions'],old['local_instructions'])
                completed={block['id']:block for block in current['blocks']
                           if block['status']=='local_preview'}
                for block_id, digest in old['golden_completed_blocks'].items():
                    with self.subTest(block=block_id):
                        self.assertIn(block_id,completed)
                        self.assertEqual(block_fingerprint(completed[block_id]),digest)
                improvement+=current['local_blocks']-old['local_blocks']
        self.assertGreater(improvement,0,'Latest decoder should recover more blocks than former implementation')

    def test_public_version_agrees_with_package_metadata(self):
        from zend_decompiler.engine import __version__
        config=(ROOT/'pyproject.toml').read_text(encoding='utf8')
        declared=re.search(r'^version\s*=\s*"([0-9.]+)"',config,re.M)
        self.assertIsNotNone(declared)
        self.assertEqual(__version__,declared.group(1))
