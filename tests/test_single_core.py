"""All active restorations use one engine; no historical API wrappers."""
import ast, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from zend_decompiler.assets import GOLDEN, OPCODE_MAP, DICTIONARY
from zend_decompiler.restore_core import restore
from zend_decompiler.engine import restore_result, __version__

class SingleCoreTests(unittest.TestCase):
    def test_single_core_wired_to_all_entrypoints(self):
        for filename in ('engine.py', 'restore_core.py', 'batch.py', 'research.py'):
            with self.subTest(filename=filename):
                tree=ast.parse((ROOT/"src"/"zend_decompiler"/filename).read_text())
                imports={node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom) and node.module}
                self.assertFalse(any(imp.startswith('zend_restore_v') for imp in imports))

    def test_no_old_python_source_modules(self):
        import re
        paths=list((ROOT/'src'/'zend_decompiler').glob('*.py'))
        self.assertFalse([p.name for p in paths if re.search(r'_v[0-9]+\.py$',p.name)])

    def test_core_matches_public_engine(self):
        import json
        files=json.loads((GOLDEN/'manifest.json').read_text())['full_candidates']
        for name in files:
            with self.subTest(name=name):
                source=ROOT/'sample_inputs'/name
                code, report=restore(source,DICTIONARY,OPCODE_MAP,version='v'+__version__.split('.')[0],trace_rules=True)
                public=restore_result(source,DICTIONARY,OPCODE_MAP)
                self.assertEqual(code,public.code)
                self.assertEqual(report['total_serialized_instructions'],public.audit['total_serialized_instructions'])
                self.assertEqual(report['groups'],public.audit['groups'])
