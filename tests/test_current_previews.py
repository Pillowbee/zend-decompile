"""Check current decoder previews without constraining earlier revisions."""
from __future__ import annotations
import re
import unittest
from pathlib import Path
from zend_decompiler.assets import OPCODE_MAP, DICTIONARY
from zend_decompiler.block_previews import run
from zend_decompiler.prefix_restore import Unsupported

ROOT = Path(__file__).resolve().parents[1]

class CurrentPreviewTests(unittest.TestCase):
    def test_current_preview_counts_are_consistent(self):
        inspected = 0
        sources = sorted((ROOT / 'sample_inputs').glob('*.php'))
        self.assertTrue(sources, 'No sample inputs')
        for source in sources:
            with self.subTest(source=source.name):
                try:
                    preview = run(source, DICTIONARY, OPCODE_MAP)
                except Unsupported:
                    # Some inputs are intentionally outside the current format.
                    continue
                inspected += 1
                blocks = preview['blocks']
                self.assertEqual(preview['source'], source.name)
                self.assertEqual(preview['local_blocks'],
                                 sum(b['status'] == 'local_preview' for b in blocks))
                self.assertEqual(preview['local_instructions'],
                                 sum(b['instruction_count'] for b in blocks
                                     if b['status'] == 'local_preview'))
                self.assertLessEqual(preview['local_instructions'], preview['total'])
                self.assertFalse(preview['executable_source'])
        self.assertGreater(inspected, 0)

    def test_public_version_agrees_with_package_metadata(self):
        from zend_decompiler.engine import __version__
        config = (ROOT / 'pyproject.toml').read_text(encoding='utf8')
        declared = re.search(r'^version\s*=\s*"([0-9.]+)"', config, re.M)
        self.assertIsNotNone(declared)
        self.assertEqual(__version__, declared.group(1))
