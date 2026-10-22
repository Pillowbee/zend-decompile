#!/usr/bin/env python3
"""Fail-closed recognition of Encoder-level call terminators.

The serialized Zend Encoder stream encodes a call to a function declared in
the same file as a terminator instruction whose op1 is an index into the
file's `header_symbols` table and whose `extended_value` is the argument
count.  The *native* opcode number for those positions stays unresolved
(140 vs 200 is not settled), so this module works on the Encoder level
only: it never rewrites `opcode_map.json` and never claims native semantics.

Every rule fails closed.  A call site that cannot be resolved without
guessing keeps the whole file in the `unsupported` state instead of
emitting a guessed call.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from .assets import ENCODER_CALL_MAP, ENCODER_CALL_EVIDENCE
from .calibrate import choose_opcode

IDENTIFIER = re.compile(rb'[A-Za-z_][A-Za-z0-9_]*\Z')
SEND_NAMES = frozenset({'SEND_VAL', 'SEND_VAR', 'SEND_VAR_NO_REF'})
# Native DO_FCALL.  The encoder stores this number in the extended_value of
# every SEND_* instruction that belongs to an encoder call.
SEND_TARGET = 60
# Operand type per native SEND name, restricted to the shapes observed in
# the supplied corpus.  A different shape is refused, never converted.
SEND_OPERAND_TYPES = {'SEND_VAL': (1, 2), 'SEND_VAR': (16,), 'SEND_VAR_NO_REF': (16,)}


class CallSiteError(ValueError):
    """A call site that cannot be resolved without guessing."""


@lru_cache(maxsize=1)
def _map_document() -> dict:
    return json.loads(ENCODER_CALL_MAP.read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def _evidence_document() -> dict:
    return json.loads(ENCODER_CALL_EVIDENCE.read_text(encoding='utf-8'))


def raw_keys() -> frozenset[str]:
    """Raw `(index mod 8):(encoded byte)` keys of encoder call terminators."""
    return frozenset(_map_document()['raw_keys'])


def evidence_document() -> dict:
    """Read-only evidence archive for the encoder call semantics."""
    return _evidence_document()


def is_call_terminator(op: dict) -> bool:
    """True when the instruction is one of the known encoder call keys."""
    return f"{op['index'] % 8}:{op['encoded_opcode']}" in raw_keys()


def opcode_name(op: dict, mapping: dict) -> str | None:
    """Native name of one decoded instruction, or None when unmapped."""
    code = choose_opcode(op, mapping)
    if code is None:
        return None
    return mapping.get('names', {}).get(str(code), {4: 'DIV'}.get(code, str(code)))


def _unused(node: dict, number: int) -> bool:
    return node.get('type') == 8 and node.get('word0') == number and node.get('word1') == 1


def recv_count(group: dict, mapping: dict) -> int | None:
    """Number of leading RECV of a function group.

    ``None`` means "signature unknown" (RECV_INIT, i.e. default arguments,
    or a non-canonical RECV run).  Such a callee can never be called.
    """
    count = 0
    for op in group['opcodes']:
        code = choose_opcode(op, mapping)
        if code == 64:  # RECV_INIT: default arguments are not covered here.
            return None
        if code != 63:  # RECV
            break
        constant = op['op1'].get('constant', {})
        if not (op['op1'].get('type') == 1 and constant.get('kind') == 'integer' and
                constant.get('value') == count + 1 and op['result'].get('type') == 16):
            return None
        count += 1
    return count


def declared_callees(parsed: dict, mapping: dict) -> dict[bytes, int | None]:
    """Every function declared in the file with its RECV count."""
    result: dict[bytes, int | None] = {}
    for group in [parsed['main']] + list(parsed['functions']):
        name = b'<main>' if group is parsed['main'] else bytes.fromhex(group['name_hex'])
        result[name] = recv_count(group, mapping)
    return result


def resolve(op: dict, ops: list[dict], mapping: dict, symbols: list[dict],
            callees: dict[bytes, int | None]) -> dict:
    """Resolve one encoder call terminator into a callable site.

    Returns a dict with the callee name, argument count and the indices of
    the SEND instructions that carry the arguments.  Raises `CallSiteError`
    with a stable reason code for every rejected shape.
    """
    index = op['index']
    # 1. Operand shape of the terminator itself.
    if not (op['op1'].get('type') == 8 and op['op1'].get('word1') == 1):
        raise CallSiteError('operand1_shape_mismatch')
    if not _unused(op['op2'], 0):
        raise CallSiteError('operand2_shape_mismatch')
    if not (op['result'].get('type') == 4 and op['result'].get('word1') in (0, 1)):
        raise CallSiteError('result_shape_mismatch')

    argc = op['extended_value']
    if not isinstance(argc, int) or argc < 0:
        raise CallSiteError('argument_count_invalid')

    # 2. The callee is named by an index into the file symbol table.
    symbol_index = op['op1']['word0']
    if not isinstance(symbol_index, int) or not (0 <= symbol_index < len(symbols)):
        raise CallSiteError('symbol_index_out_of_bounds')
    symbol = symbols[symbol_index]
    if symbol.get('index') != symbol_index:
        raise CallSiteError('symbol_table_index_mismatch')
    try:
        name = bytes.fromhex(symbol['name_hex'])
    except (ValueError, TypeError):
        raise CallSiteError('invalid_symbol_encoding') from None
    if not IDENTIFIER.fullmatch(name):
        raise CallSiteError('invalid_identifier')

    # 3. The callee must be a function declared in this very file, and the
    #    declared signature must match the encoded argument count.
    if name not in callees:
        raise CallSiteError('callee_not_declared_in_file')
    signature = callees[name]
    if signature is None:
        raise CallSiteError('callee_signature_unknown')
    if signature != argc:
        raise CallSiteError('arity_signature_mismatch')

    # 4. The arguments are the SEND instructions right before the terminator.
    if argc and index - argc < 0:
        raise CallSiteError('argument_run_out_of_range')
    sends = ops[index - argc:index] if argc else []
    for position, send in enumerate(sends, start=1):
        name_of_send = opcode_name(send, mapping)
        if name_of_send not in SEND_NAMES:
            raise CallSiteError('non_send_in_argument_run')
        if not _unused(send['result'], 0):
            raise CallSiteError('send_result_mismatch')
        if not _unused(send['op2'], position):
            raise CallSiteError('send_position_or_marker_mismatch')
        if send['extended_value'] != SEND_TARGET:
            raise CallSiteError('send_target_mismatch')
        if send['op1'].get('type') not in SEND_OPERAND_TYPES[name_of_send]:
            raise CallSiteError('send_operand_shape_mismatch')
    # 5. No unfinished argument run may precede the accepted one.
    if index - argc - 1 >= 0:
        previous = ops[index - argc - 1]
        if opcode_name(previous, mapping) in SEND_NAMES:
            raise CallSiteError('unclosed_prior_send')
    return {'name': name, 'argc': argc, 'symbol_index': symbol_index,
            'send_indices': [send['index'] for send in sends],
            'callee_signature': signature}
