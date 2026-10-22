"""Only unique immutable PHP inputs, golden outputs, own corpus and research fragments.

Protected inputs and recovered PHP candidates are never executed.
"""
from __future__ import annotations
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def signature(content: bytes) -> bytes:
    # Historical output headers varied by version, not by recovered PHP body.
    return re.sub(rb'/\* EXPERIMENTAL Zend recovery v\d+\. Verify before use\. \*/',
                  b'/* EXPERIMENTAL Zend recovery vX. Verify before use. */', content)


class PHPArtifactLayout(unittest.TestCase):
    # The protected local corpus of the owner is not part of the repository:
    # it is ignored by git and holds real files of the site, so the layout
    # checks of the repository must not look at it.
    LOCAL_CORPUS = ('sample_inputs', 'pipeshop')

    def _repository_php_files(self):
        for path in ROOT.rglob('*.php'):
            if '__pycache__' in path.parts:
                continue
            relative = path.relative_to(ROOT)
            if relative.parts[:len(self.LOCAL_CORPUS)] == self.LOCAL_CORPUS:
                continue
            yield path

    def test_no_old_batch_or_generated_snapshots(self):
        self.assertFalse((ROOT / 'generated').exists())
        self.assertFalse((ROOT / 'examples').exists())
        self.assertFalse((ROOT / 'user_candidate_v19.php').exists())

    def test_only_unique_php_files_remain(self):
        seen = {}
        for p in self._repository_php_files():
            digest = signature(p.read_bytes())
            with self.subTest(path=str(p.relative_to(ROOT))):
                self.assertNotIn(digest, seen,
                                 f'{p.relative_to(ROOT)} repeats {seen.get(digest)}')
            seen[digest] = p.relative_to(ROOT)

    def test_preserved_categories(self):
        self.assertEqual(len(list((ROOT / 'sample_inputs').glob('*.php'))), 11)
        self.assertEqual(len(list((ROOT / 'golden/reference/code').glob('*.php'))), 10)
        self.assertEqual(len(list((ROOT / 'corpus/own_sources').glob('*.php'))), 5)
        self.assertEqual(len(list((ROOT / 'research/fragments').glob('*.php'))), 12)
        self.assertEqual(len(list(self._repository_php_files())), 38)


if __name__ == '__main__':
    unittest.main()
