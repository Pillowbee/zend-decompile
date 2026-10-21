"""Source layout and import-boundary regression checks (no input PHP execution)."""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'src' / 'zend_decompiler'


class SourceLayoutTests(unittest.TestCase):
    def test_code_is_only_inside_installed_package(self):
        self.assertTrue((PACKAGE / '__init__.py').is_file())
        self.assertTrue((PACKAGE / '__main__.py').is_file())
        self.assertFalse(list(ROOT.glob('*.py')), 'Python sources must not live in repository root')
        self.assertGreaterEqual(len(list(PACKAGE.glob('*.py'))), 20)

    def test_package_imports_are_relative(self):
        names = {p.stem for p in PACKAGE.glob('*.py')}
        for file in PACKAGE.glob('*.py'):
            with self.subTest(module=file.name):
                tree = ast.parse(file.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module in names:
                        self.assertEqual(node.level, 1, f'{file.name}: internal import must be relative')

    def test_install_and_cli_metadata(self):
        metadata = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
        self.assertIn('where = ["src"]', metadata)
        self.assertIn('zend-decompiler = "zend_decompiler.cli:main"', metadata)
        self.assertIn('networkx>=2.8', metadata)
        self.assertTrue((ROOT / 'data' / 'opcodes' / 'opcode_map.json').is_file())
        self.assertTrue((ROOT / 'golden' / 'reference' / 'manifest.json').is_file())


if __name__ == '__main__':
    unittest.main()
