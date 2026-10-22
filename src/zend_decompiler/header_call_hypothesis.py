"""Experimental read-only evidence check for header-indexed local calls.

This checks a narrow pattern in *existing* Zend Encoder samples; it neither
reinterprets native opcode 140 nor changes the mapping, parser, or PHP emitter.
A structural match is NOT independent confirmation of Encoder semantics.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .assets import DICTIONARY, OPCODE_MAP
from .calibrate import choose_opcode
from .cfg import cfg_for_group
from .readonly_dataflow import _validated_evidence
from .serial_parser import FormatError, decompress_encoded, parse_binary

# Exact raw keys historically mapped to 140; do not extrapolate to other keys.
DISPUTED_KEYS = frozenset({'0:26', '1:7', '2:230', '3:160',
                           '4:250', '5:216', '6:226', '7:125'})
SEND_OPCODES = frozenset({65, 66})  # Only observed SEND_VAL and SEND_VAR shapes.
INIT_OPCODES = frozenset({59, 112, 113})
CLOSE_OPCODES = frozenset({60, 61})
IDENTIFIER = re.compile(rb'[A-Za-z_][A-Za-z0-9_]*\Z')


def _key(op: dict) -> str:
    return f'{op["index"] % 8}:{op["encoded_opcode"]}'


def _unused(node: dict, number: int) -> bool:
    return node.get('type') == 8 and node.get('word0') == number and node.get('word1') == 1


def _native(op: dict, mapping: dict) -> int | None:
    return choose_opcode(op, mapping)


def _signature(function: dict, mapping: dict) -> int | None:
    """Number of *required* leading RECV; reject defaults/irregular signatures."""
    count = 0
    for op in function['opcodes']:
        native = _native(op, mapping)
        if native == 64:  # RECV_INIT: default arguments not covered by this research.
            return None
        if native != 63:
            break
        c = op['op1'].get('constant', {})
        if (op['op1'].get('type') != 1 or c.get('kind') != 'integer' or
                c.get('value') != count + 1 or op['result'].get('type') != 16):
            return None
        count += 1
    return count


def _pending_initialized_call(ops: list[dict], block_start: int,
                              before_sends: int, mapping: dict) -> bool:
    """Reject an unresolved initialized call in this *single* basic block.

    Does not attempt cross-block propagation. A negative answer is only a
    syntactic screen, never proof of PHP call-stack equivalence.
    """
    pending = 0
    for op in ops[block_start:before_sends]:
        native = _native(op, mapping)
        if native in INIT_OPCODES:
            pending += 1
        elif native in CLOSE_OPCODES and pending:
            pending -= 1
    return bool(pending)


def analyze_parsed(parsed: dict, mapping: dict, evidence: dict) -> dict:
    """Return literal-free, experimental diagnostics; do not mutate inputs."""
    symbols = parsed.get('header_symbols', [])
    functions: dict[bytes, list[dict]] = {}
    for function in parsed['functions']:
        functions.setdefault(bytes.fromhex(function['name_hex']), []).append(function)
    groups = [('<main>', parsed['main'])]
    groups.extend((bytes.fromhex(f['name_hex']).decode('cp1251', errors='replace'), f)
                  for f in parsed['functions'])
    rows: list[dict] = []
    for group_name, group in groups:
        ops = group['opcodes']
        disputed = [op for op in ops
                    if _key(op) in DISPUTED_KEYS and _native(op, mapping) == 140]
        if not disputed:
            continue
        # Separate, untrusted *views*, never changes to the parsed instructions.
        cfg_ops = [{**op, 'decoded_opcode': (None if _key(op) in DISPUTED_KEYS else
                                             _native(op, mapping))}
                   for op in ops]
        other_unknown = [op['index'] for op in cfg_ops
                         if op['decoded_opcode'] is None and _key(op) not in DISPUTED_KEYS]
        cfg = None
        cfg_problem = None
        if other_unknown:
            cfg_problem = 'other_unknown_opcodes'
        else:
            try:
                cfg = cfg_for_group(group_name, {'opcodes': cfg_ops})
            except (FormatError, AssertionError, KeyError, ValueError):
                cfg_problem = 'unmodeled_or_invalid_cfg'
        for op in disputed:
            index = op['index']
            key = _key(op)
            row = {'group': group_name, 'index': index, 'byte_offset': op['offset'],
                   'line': op['line'], 'encoded_key': key,
                   'mapping_native_id_hypothesis': 140,
                   'evidence_status': evidence.get(key, {}).get('status', 'absent'),
                   'status': 'rejected', 'reason': None,
                   'callee': None, 'callee_signature': None,
                   'argument_count': op['extended_value'],
                   'cross_validated': False,
                   'send_indices': [], 'basic_block': None}
            rows.append(row)

            def reject(reason: str, *, indeterminate: bool = False) -> None:
                row['reason'] = reason
                if indeterminate:
                    row['status'] = 'unverifiable_cfg'

            ev = evidence.get(key, {})
            if ev.get('status') != 'unknown' or ev.get('opcode') != 140:
                reject('not_unconfirmed_140_evidence')
                continue
            if not (_unused(op['op2'], 0) and
                    op['op1'].get('type') == 8 and op['op1'].get('word1') == 1 and
                    op['result'].get('type') == 4 and
                    op['result'].get('word1') in (0, 1)):
                reject('operand_shape_mismatch')
                continue
            sym_ix = op['op1']['word0']
            if not isinstance(sym_ix, int) or not (0 <= sym_ix < len(symbols)):
                reject('symbol_index_out_of_bounds')
                continue
            symbol = symbols[sym_ix]
            if symbol.get('index') != sym_ix:
                reject('symbol_table_index_mismatch')
                continue
            try:
                name = bytes.fromhex(symbol['name_hex'])
            except (ValueError, TypeError):
                reject('invalid_symbol_encoding')
                continue
            if not IDENTIFIER.fullmatch(name):
                reject('invalid_identifier')
                continue
            row['callee'] = name.decode('ascii')
            definitions = functions.get(name, [])
            if len(definitions) != 1:
                reject('callee_not_uniquely_defined_locally')
                continue
            signature = _signature(definitions[0], mapping)
            if signature is None:
                reject('unverifiable_signature')
                continue
            row['callee_signature'] = signature
            argc = op['extended_value']
            if not isinstance(argc, int) or argc < 0 or argc != signature:
                reject('arity_signature_mismatch')
                continue
            row['cross_validated'] = True
            if cfg is None:
                reject(cfg_problem or 'cfg_unavailable', indeterminate=True)
                continue
            block = next((b for b in cfg['basic_blocks']
                          if b['first'] <= index <= b['last']), None)
            if block is None or not block.get('reachable', False):
                reject('call_site_not_reachable', indeterminate=True)
                continue
            row['basic_block'] = block['id']
            if index - argc < block['first']:
                reject('send_crosses_basic_block')
                continue
            sends = ops[index - argc:index]
            row['send_indices'] = [x['index'] for x in sends]
            # The observed format has exactly these argument shapes; no
            # conversion or speculative handling of SEND_REF or SEND_VAR_NO_REF.
            valid = True
            for position, send in enumerate(sends, start=1):
                native = _native(send, mapping)
                operand = send['op1']
                if native not in SEND_OPCODES:
                    reject('non_send_in_argument_run');valid = False;break
                if native == 65 and operand['type'] not in (1, 2):
                    reject('send_val_shape_mismatch');valid = False;break
                if native == 66 and operand['type'] != 16:
                    reject('send_var_shape_mismatch');valid = False;break
                if not _unused(send['result'], 0):
                    reject('send_result_mismatch');valid = False;break
                if not _unused(send['op2'], position):
                    reject('send_position_or_marker_mismatch');valid = False;break
                if send['extended_value'] != 60:
                    reject('send_target_mismatch');valid = False;break
            if not valid:
                continue
            if index - argc > block['first'] and _native(ops[index - argc - 1], mapping) in SEND_OPCODES:
                reject('unclosed_prior_send')
                continue
            if _pending_initialized_call(ops, block['first'], index - argc, mapping):
                reject('unfinished_initialized_call')
                continue
            # The CFG is provisional: disputed instructions are treated as
            # non-branching *for this structural screen only*. Report this.
            row['status'] = 'experimental_structural_match'
            row['reason'] = 'consistent_if_disputed_instruction_is_non_branching'
    return {'kind': 'EXPERIMENTAL_READ_ONLY_HEADER_INDEXED_CALLS',
            'php_generated': False, 'semantic_equivalence_proven': False,
            'map_rewritten': False, 'disputed_opcode_promoted': False,
            'cfg_note': 'Basic-block check assumes disputed call-site is non-branching; not a verified CFG.',
            'encoder_level_note': ('Since v29 the decoder recognises this call form on the Encoder level '
                                   'only (file symbol table plus encoded argument count). The native '
                                   'opcode number of these positions stays unresolved and the native '
                                   'opcode map is not rewritten.'),
            'cross_validation_note': ('cross_validated marks the two independent agreements: the symbol '
                                      'index names a function declared in the same file and the encoded '
                                      'argument count equals the callee RECV count.'),
            'observations': rows}


def analyze_file(source: Path, dictionary: Path = DICTIONARY,
                 mapping_path: Path = OPCODE_MAP) -> dict:
    """Validate file consistency and perform offline parsing without PHP execution."""
    evidence = _validated_evidence(mapping_path)
    mapping = json.loads(mapping_path.read_text(encoding='utf-8'))
    streams = decompress_encoded(source, dictionary.read_bytes())
    if len(streams) != 1:
        raise FormatError('Expected exactly one encoded stream')
    report = analyze_parsed(parse_binary(streams[0][1]), mapping, evidence)
    report['file'] = source.name
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', type=Path, nargs='+')
    parser.add_argument('--dictionary', type=Path, default=DICTIONARY)
    parser.add_argument('--map', type=Path, default=OPCODE_MAP)
    parser.add_argument('-o', '--output', required=True, type=Path)
    args = parser.parse_args()
    reports = [analyze_file(x, args.dictionary, args.map) for x in args.sources]
    args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n',
                           encoding='utf-8')
    for report in reports:
        counts = {status: sum(x['status'] == status for x in report['observations'])
                  for status in ('experimental_structural_match', 'unverifiable_cfg', 'rejected')}
        print(json.dumps({'file': report['file'], 'counts': counts}, ensure_ascii=False))


if __name__ == '__main__':
    main()
