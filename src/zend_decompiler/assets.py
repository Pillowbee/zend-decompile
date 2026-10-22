"""Stable paths to preserved, immutable research fixtures and active opcode map.

The dates/versions embedded in historic evidence filenames are provenance,
not import identifiers or constraints on the test suite.
"""
from pathlib import Path
import sys
BASE = Path(__file__).resolve().parents[2]  # project checkout
DATA_DIR = BASE if (BASE / 'zend_verified_dictionary.bin').exists() else Path(sys.prefix) / 'share' / 'zend-decompiler'
OPCODE_DIR = BASE / 'data' / 'opcodes' if (BASE / 'data' / 'opcodes' / 'opcode_map.json').exists() else Path(sys.prefix) / 'share' / 'zend-decompiler' / 'opcodes'
OPCODE_MAP = OPCODE_DIR / 'opcode_map.json'
OPCODE_METADATA = OPCODE_MAP.with_name(OPCODE_MAP.name + '.meta.json')
# Encoder-level call semantics.  Kept apart from the native opcode map:
# the native number for these positions is unresolved.
ENCODER_CALL_MAP = OPCODE_DIR / 'encoder_call_map.json'
ENCODER_CALL_METADATA = ENCODER_CALL_MAP.with_name(ENCODER_CALL_MAP.name + '.meta.json')
ENCODER_CALL_EVIDENCE = OPCODE_DIR / 'encoder_call_evidence.json'
# Encoder opcode position rule.  An empirical model of how the encoded byte
# of an opcode depends on the instruction position.
ENCODER_OPCODE_BASE = OPCODE_DIR / 'encoder_opcode_base.json'
ENCODER_OPCODE_METADATA = ENCODER_OPCODE_BASE.with_name(ENCODER_OPCODE_BASE.name + '.meta.json')
ENCODER_OPCODE_EVIDENCE = OPCODE_DIR / 'encoder_opcode_evidence.json'
# Saved PHP 5.2 family headers.  Used to validate a predicted opcode against
# the operand types of its native handler.
PHP52_VM_DEF = BASE / 'reference_headers_php52_candidate' / 'zend_vm_def.h'
PHP52_VM_OPCODES = BASE / 'reference_headers_php52_candidate' / 'zend_vm_opcodes.h'
DICTIONARY = DATA_DIR / 'zend_verified_dictionary.bin'
GOLDEN = BASE / 'golden' / 'reference'
SCHEMAS = BASE / 'schemas'
ALIGNMENT_FIXTURE = BASE / 'data' / 'research' / 'alignment.json'
BATCH_REPORT_FIXTURE = BASE / 'tests' / 'fixtures' / 'batch_report.json'
