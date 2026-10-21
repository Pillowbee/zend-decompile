"""Stable paths to preserved, immutable research fixtures and active opcode map.

The dates/versions embedded in historic evidence filenames are provenance,
not import identifiers or constraints on the test suite.
"""
from pathlib import Path
import sys
BASE = Path(__file__).resolve().parent
DATA_DIR = BASE if (BASE / 'zend_verified_dictionary.bin').exists() else Path(sys.prefix) / 'share' / 'zend-decompiler'
OPCODE_MAP = DATA_DIR / 'opcode_map_observed_v20.json'
OPCODE_METADATA = OPCODE_MAP.with_name(OPCODE_MAP.name + '.meta.json')
DICTIONARY = DATA_DIR / 'zend_verified_dictionary.bin'
GOLDEN = BASE / 'golden' / 'reference'
SCHEMAS = BASE / 'schemas'
ALIGNMENT_FIXTURE = BASE / 'alignment_audit_v25.json'
BATCH_REPORT_FIXTURE = BASE / 'examples' / 'batch_v23' / 'batch_report.json'
