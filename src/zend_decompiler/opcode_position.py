#!/usr/bin/env python3
"""Encoder opcode position rule: native opcode from a position-shifted byte.

The serialized stream stores the opcode of an instruction in a byte whose
value depends on the instruction position.  For every observed byte the
native opcode equals ``base - (instruction index mod 8)``, where ``base`` is
a property of the byte alone.  The rule reproduces the whole empirical map
and predicts the positions the map has never seen.

The rule is an empirical model, not an independent proof:

* the empirical map stays authoritative for every key it contains;
* the rule is used only where the map has no entry;
* loading the rule re-checks it against the empirical map and refuses to
  work on any contradiction.

The native semantics of a predicted opcode are not established by the rule.
A predicted instruction still needs its operand shape to be compatible with
the PHP 5.2 handler of the predicted opcode before it may be decoded.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .assets import (ENCODER_OPCODE_BASE, ENCODER_OPCODE_EVIDENCE, ENCODER_OPCODE_METADATA,
                    OPCODE_MAP, PHP52_VM_DEF)

OPERAND_TYPE_NAMES = {1: 'CONST', 16: 'CV', 8: 'UNUSED', 2: 'TMP', 4: 'VAR'}


class PositionRuleError(ValueError):
    """The position rule contradicts the empirical opcode map."""


@lru_cache(maxsize=1)
def _rule_document() -> dict:
    document = json.loads(ENCODER_OPCODE_BASE.read_text(encoding='utf-8'))
    metadata = json.loads(ENCODER_OPCODE_METADATA.read_text(encoding='utf-8'))
    if metadata.get('mapping_file') != ENCODER_OPCODE_BASE.name:
        raise PositionRuleError('Position rule metadata names a different rule file')
    # The rule is only usable while it still reproduces the empirical map.
    verify_against_map(json.loads(OPCODE_MAP.read_text(encoding='utf-8')))
    return document


@lru_cache(maxsize=1)
def _handler_signatures() -> dict:
    """Operand type signatures of the PHP 5.2 handlers, by native opcode."""
    signatures: dict[int, dict] = {}
    if not PHP52_VM_DEF.is_file():
        return signatures
    pattern = re.compile(r'ZEND_VM_HANDLER\((\d+),\s*(\w+),\s*([\w|]+),\s*([\w|]+)\)')
    for line in PHP52_VM_DEF.read_text(errors='replace').splitlines():
        match = pattern.match(line)
        if match:
            signatures[int(match.group(1))] = {
                'name': match.group(2),
                'op1': match.group(3).split('|'),
                'op2': match.group(4).split('|')}
    return signatures


def rule_document() -> dict:
    """The loaded position rule, including its byte base table."""
    return _rule_document()


def base_for(byte: int) -> int | None:
    """Base value of one encoded opcode byte, or None when it is unknown."""
    bases = _rule_document().get('byte_bases', {})
    value = bases.get(str(byte))
    return value if isinstance(value, int) else None


def predict(op: dict) -> int | None:
    """Raw position-rule prediction for one instruction, without any guard."""
    base = base_for(op['encoded_opcode'])
    if base is None:
        return None
    value = base - (op['index'] % 8)
    return value if value >= 0 else None


def shape_compatible(op: dict, opcode: int) -> bool:
    """True when the operands fit the PHP 5.2 handler of the given opcode.

    The handler signatures come from the saved PHP 5.2 family header, which
    is independent of the archived handler traces.  A missing header or an
    unknown handler refuses the prediction.
    """
    signatures = _handler_signatures()
    handler = signatures.get(opcode)
    if handler is None:
        return False
    for position, allowed in (('op1', handler['op1']), ('op2', handler['op2'])):
        node = op.get(position) or {}
        name = OPERAND_TYPE_NAMES.get(node.get('type'))
        if name is None:
            return False
        if 'ANY' not in allowed and name not in allowed:
            return False
    return True


def opcode_for(op: dict) -> int | None:
    """Native opcode predicted for one instruction, guarded by its shape.

    The prediction is refused when the operand shape does not fit the PHP 5.2
    handler of the predicted opcode: a prediction is never trusted blindly.
    """
    value = predict(op)
    if value is None:
        return None
    return value if shape_compatible(op, value) else None


def verify_against_map(mapping: dict) -> dict:
    """Check the rule against the empirical map; refuse on any contradiction.

    Returns a summary of the check.  Raises `PositionRuleError` when a key
    of the empirical map is not reproduced by the rule.
    """
    bases = json.loads(ENCODER_OPCODE_BASE.read_text(encoding='utf-8')).get('byte_bases', {})
    checked = 0
    uncovered = []
    contradictions = []
    for key, mapped in mapping.get('opcodes', {}).items():
        position, byte = key.split(':')
        base = bases.get(byte)
        if base is None:
            uncovered.append(key)
            continue
        predicted = base - int(position)
        checked += 1
        if predicted != mapped:
            contradictions.append({'key': key, 'mapped': mapped, 'predicted': predicted})
    if contradictions:
        raise PositionRuleError(
            'Position rule contradicts the empirical opcode map: '
            + json.dumps(contradictions[:8], ensure_ascii=False))
    return {'checked_keys': checked, 'uncovered_keys': sorted(uncovered),
            'contradictions': 0}


def evidence_document() -> dict:
    """Read-only evidence archive of the position rule."""
    return json.loads(Path(ENCODER_OPCODE_EVIDENCE).read_text(encoding='utf-8'))
