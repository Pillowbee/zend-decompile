"""Encoder-level call terminators: positive evidence and fail-closed negatives.

Never executes a PHP input or a generated candidate.  The native opcode map
is not rewritten: the native number of these positions stays unresolved and
only the Encoder level (file symbol table + encoded argument count) is used.
"""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from zend_decompiler.assets import DICTIONARY, ENCODER_CALL_EVIDENCE, OPCODE_MAP
from zend_decompiler.calibrate import choose_opcode
from zend_decompiler.encoder_calls import (CallSiteError, declared_callees, is_call_terminator,
                                           raw_keys, recv_count, resolve)
from zend_decompiler.engine import restore_result
from zend_decompiler.prefix_restore import Decoder, Unsupported
from zend_decompiler.serial_parser import Reader, decompress_encoded, parse_binary

SAMPLE = ROOT / 'sample_inputs'
LINKS = SAMPLE / 'links_fun(1).php'
MAPPING = json.loads(OPCODE_MAP.read_text(encoding='utf-8'))


# --- synthetic instruction helpers (no PHP sample is added to the corpus) ---

def const(value: int) -> dict:
    return {'type': 1, 'constant': {'kind': 'integer', 'value': value}}


def cv(index: int) -> dict:
    return {'type': 16, 'word0': index, 'word1': 0}


def unused(first: int, second: int = 1) -> dict:
    return {'type': 8, 'word0': first, 'word1': second}


def tmp(first: int, second: int = 0) -> dict:
    return {'type': 2, 'word0': first, 'word1': second}


def var(first: int, second: int = 0) -> dict:
    return {'type': 4, 'word0': first, 'word1': second}


def instruction(index: int, byte: int, op1: dict, op2: dict, result: dict,
                extended: int = 0) -> dict:
    return {'index': index, 'offset': 0, 'size': 0, 'encoded_opcode': byte,
            'decoded_opcode': None, 'result': result, 'op1': op1, 'op2': op2,
            'extended_value': extended, 'line': 1}


def terminator(index: int, symbol_index: int, argc: int) -> dict:
    """A call terminator on one of the documented raw keys."""
    byte = int(raw_key_for(index).split(':')[1])
    return instruction(index, byte, unused(symbol_index), unused(0), var(0, 1), argc)


def raw_key_for(index: int) -> str:
    for key in sorted(raw_keys()):
        position, byte = key.split(':')
        if int(position) == index % 8:
            return key
    raise AssertionError('no documented raw key for position ' + str(index % 8))


def send(index: int, operand: dict, position: int, name: str = 'SEND_VAR') -> dict:
    """A SEND instruction of the documented call protocol."""
    code = {'SEND_VAL': 65, 'SEND_VAR': 66}[name]
    byte = send_byte(index % 8, code)
    op = instruction(index, byte, operand, unused(position), unused(0), 60)
    op['decoded_opcode'] = code
    op['_decoded_name'] = name
    return op


def send_byte(position: int, code: int) -> int:
    """Encoded byte of a SEND opcode observed at the given stream position."""
    for key, value in MAPPING['opcodes'].items():
        stream_position, byte = key.split(':')
        if int(stream_position) == position and value == code:
            return int(byte)
    raise AssertionError(f'no observed SEND byte for opcode {code} at position {position}')


def non_send_byte(position: int) -> int:
    """Encoded byte of an opcode that is not a SEND at the given position."""
    for key, value in MAPPING['opcodes'].items():
        stream_position, byte = key.split(':')
        if int(stream_position) == position and value == 43:  # JMPZ
            return int(byte)
    raise AssertionError('no observed non-SEND byte at position ' + str(position))


# --- tampered input helpers ----------------------------------------------

def find_stream_offset(buf: bytes, dictionary: bytes) -> int:
    checksum = zlib.adler32(dictionary)
    for index in range(len(buf) - 6):
        cmf, flg = buf[index:index + 2]
        if (cmf & 15) != 8 or (cmf >> 4) > 7 or ((cmf << 8) + flg) % 31 != 0 or not (flg & 0x20):
            continue
        if int.from_bytes(buf[index + 2:index + 6], 'big') != checksum:
            continue
        return index
    raise AssertionError('no zlib stream with the project dictionary')


def raw_stream(path: Path) -> tuple[bytes, bytes, int]:
    buf = path.read_bytes()
    offset = find_stream_offset(buf, DICTIONARY.read_bytes())
    streams = decompress_encoded(path, DICTIONARY.read_bytes())
    assert len(streams) == 1
    return buf, streams[0][1], offset


def op1_digit_offset(raw: bytes, instruction_offset: int) -> int:
    """Offset of the first digit of the op1 word0 field of one instruction."""
    reader = Reader(raw, instruction_offset)
    reader.byte()      # opcode byte
    reader.node()      # result operand
    reader.byte()      # op1 operand type
    length = raw[reader.pos]
    assert 2 <= length <= 24
    return reader.pos + 1


def tamper_symbol_index(raw: bytes, instruction_offset: int, replacement: str) -> bytes:
    position = op1_digit_offset(raw, instruction_offset)
    return raw[:position] + replacement.encode('ascii') + raw[position + len(replacement):]


def write_tampered(tmp_path: Path, raw: bytes, prefix: bytes) -> Path:
    compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED,
                                  zlib.MAX_WBITS, zlib.DEF_MEM_LEVEL,
                                  zlib.Z_DEFAULT_STRATEGY, zdict=DICTIONARY.read_bytes())
    target = tmp_path / 'tampered.php'
    target.write_bytes(prefix + compressor.compress(raw) + compressor.flush())
    return target


class EncoderCallEvidenceTests(unittest.TestCase):
    def test_every_corpus_call_site_is_resolved_and_cross_validated(self):
        document = json.loads(ENCODER_CALL_EVIDENCE.read_text(encoding='utf-8'))
        self.assertEqual(document['summary']['call_sites'], 18)
        self.assertEqual(document['summary']['rejected'], 0)
        self.assertEqual(document['summary']['argc_matches_recv'], 18)
        for identifier, entry in document['entries'].items():
            with self.subTest(site=identifier):
                self.assertEqual(entry['status'], 'inferred')
                self.assertTrue(entry['cross_validated'])
                self.assertTrue(entry['checks']['symbol_resolved'])
                self.assertTrue(entry['checks']['callee_declared_in_file'])
                self.assertTrue(entry['checks']['argc_matches_recv'])
                self.assertEqual(entry['argument_count'], entry['callee_signature'])

    def test_call_sites_resolve_against_the_live_corpus(self):
        total = 0
        for path in sorted(SAMPLE.glob('*.php')):
            if b'@Zend;' not in path.read_bytes()[:40]:
                continue
            streams = decompress_encoded(path, DICTIONARY.read_bytes())
            if len(streams) != 1:
                continue
            parsed = parse_binary(streams[0][1])
            symbols = parsed.get('header_symbols', [])
            callees = declared_callees(parsed, MAPPING)
            groups = [('<main>', parsed['main'])] + [
                (bytes.fromhex(f['name_hex']).decode('ascii'), f) for f in parsed['functions']]
            for group_name, group in groups:
                ops = group['opcodes']
                for op in ops:
                    if not is_call_terminator(op):
                        continue
                    total += 1
                    site = resolve(op, ops, MAPPING, symbols, callees)
                    self.assertEqual(site['argc'], op['extended_value'])
                    self.assertIn(site['name'], callees)
                    self.assertEqual(callees[site['name']], site['argc'])
                    self.assertEqual(len(site['send_indices']), site['argc'])
        self.assertEqual(total, 18)

    def test_symbol_table_names_the_called_local_functions(self):
        streams = decompress_encoded(LINKS, DICTIONARY.read_bytes())
        parsed = parse_binary(streams[0][1])
        names = [bytes.fromhex(s['name_hex']).decode('ascii') for s in parsed['header_symbols']]
        self.assertEqual(names, ['count_ln', 'send_mail'])
        declared = {bytes.fromhex(f['name_hex']).decode('ascii') for f in parsed['functions']}
        self.assertTrue(set(names) <= declared)

    def test_recv_count_is_unknown_for_default_arguments(self):
        streams = decompress_encoded(LINKS, DICTIONARY.read_bytes())
        parsed = parse_binary(streams[0][1])
        main = parsed['main']
        # <main> has no RECV; a function group reports its leading RECV count.
        self.assertEqual(recv_count(main, MAPPING), 0)
        groups = {bytes.fromhex(f['name_hex']): f for f in parsed['functions']}
        self.assertEqual(recv_count(groups[b'count_ln'], MAPPING), 2)
        self.assertEqual(recv_count(groups[b'send_mail'], MAPPING), 2)


class EncoderCallRestorationTests(unittest.TestCase):
    def test_links_fun_is_now_a_full_candidate(self):
        result = restore_result(LINKS, DICTIONARY, OPCODE_MAP)
        self.assertEqual(result.status, 'candidate_generated', result.reason)
        self.assertIsNotNone(result.code)
        self.assertIn(b'send_mail($url_mail, $id_link);', result.code)
        self.assertIn(b'count_ln($id_ln_groups, 0)', result.code)
        self.assertEqual(result.audit['rule_usage']['ENCODER_CALL'], 2)
        self.assertEqual(result.audit['encoder_call_count'], 2)
        callees = sorted(site['callee'] for site in result.audit['encoder_call_sites'])
        self.assertEqual(callees, ['count_ln', 'send_mail'])

    def test_disputed_native_keys_keep_unknown_confidence(self):
        result = restore_result(LINKS, DICTIONARY, OPCODE_MAP)
        self.assertEqual(result.audit['confidence_counts']['unknown'], 2)
        self.assertEqual(result.audit['confidence_counts']['confirmed'], 0)
        self.assertEqual(result.audit['mapping_sha256'],
                         hashlib.sha256(OPCODE_MAP.read_bytes()).hexdigest())

    def test_native_opcode_map_is_untouched(self):
        mapping = json.loads(OPCODE_MAP.read_text(encoding='utf-8'))
        for key in raw_keys():
            self.assertEqual(mapping['opcodes'][key], 140)
        self.assertEqual(len(raw_keys()), 8)
        self.assertEqual(sorted(raw_keys()),
                         ['0:26', '1:7', '2:230', '3:160', '4:250', '5:216', '6:226', '7:125'])


class EncoderCallFailClosedTests(unittest.TestCase):
    """Every rejected shape must refuse instead of guessing a call."""

    def setUp(self) -> None:
        self.symbols = [{'index': 0, 'name_hex': 'count_ln'.encode('ascii').hex(),
                         'hash_signed': 0},
                        {'index': 1, 'name_hex': 'send_mail'.encode('ascii').hex(),
                         'hash_signed': 0}]
        self.callees = {b'count_ln': 2, b'send_mail': 2}

    def _ops(self, argc: int = 2) -> list[dict]:
        ops = [send(0, cv(0), 1), send(1, const(0), 2, name='SEND_VAL')]
        ops.append(terminator(2, 1, argc))
        return ops

    def _reject(self, ops, symbols=None, callees=None, reason=None) -> None:
        with self.assertRaises(CallSiteError) as caught:
            resolve(ops[-1], ops, MAPPING,
                    self.symbols if symbols is None else symbols,
                    self.callees if callees is None else callees)
        if reason is not None:
            self.assertEqual(str(caught.exception), reason)

    def test_accepts_a_consistent_call_site(self):
        site = resolve(self._ops()[-1], self._ops(), MAPPING, self.symbols, self.callees)
        self.assertEqual(site['name'], b'send_mail')
        self.assertEqual(site['argc'], 2)
        self.assertEqual(site['symbol_index'], 1)
        self.assertEqual(site['send_indices'], [0, 1])

    def test_rejects_symbol_index_out_of_bounds(self):
        self._reject(self._ops(), symbols=[self.symbols[0]], reason='symbol_index_out_of_bounds')

    def test_rejects_callee_not_declared_in_file(self):
        self._reject(self._ops(), callees={b'count_ln': 2},
                     reason='callee_not_declared_in_file')

    def test_rejects_unknown_callee_signature(self):
        self._reject(self._ops(), callees={b'count_ln': 2, b'send_mail': None},
                     reason='callee_signature_unknown')

    def test_rejects_arity_mismatch(self):
        self._reject(self._ops(argc=3), reason='arity_signature_mismatch')

    def test_rejects_non_send_in_the_argument_run(self):
        ops = self._ops()
        ops[0]['encoded_opcode'] = non_send_byte(0)
        self._reject(ops, reason='non_send_in_argument_run')

    def test_rejects_unclosed_prior_send(self):
        # A third SEND precedes the accepted run: the earlier run is not closed.
        ops = [send(0, cv(0), 1), send(1, cv(1), 1), send(2, cv(2), 2),
               terminator(3, 1, 2)]
        self._reject(ops, reason='unclosed_prior_send')

    def test_rejects_send_position_mismatch(self):
        ops = self._ops()
        ops[1]['op2'] = unused(3)
        self._reject(ops, reason='send_position_or_marker_mismatch')

    def test_rejects_send_target_mismatch(self):
        ops = self._ops()
        ops[1]['extended_value'] = 61
        self._reject(ops, reason='send_target_mismatch')

    def test_rejects_send_operand_shape_mismatch(self):
        ops = self._ops()
        ops[0]['op1'] = const(1)  # SEND_VAR with a constant operand
        self._reject(ops, reason='send_operand_shape_mismatch')

    def test_rejects_invalid_callee_identifier(self):
        symbols = [dict(self.symbols[0]), dict(self.symbols[1])]
        symbols[1]['name_hex'] = 'not an identifier'.encode('ascii').hex()
        self._reject(self._ops(), symbols=symbols, reason='invalid_identifier')

    def test_rejects_terminator_operand_shape_mismatch(self):
        ops = self._ops()
        ops[-1]['op1'] = tmp(1)
        self._reject(ops, reason='operand1_shape_mismatch')
        ops = self._ops()
        ops[-1]['op2'] = unused(1)
        self._reject(ops, reason='operand2_shape_mismatch')
        ops = self._ops()
        ops[-1]['result'] = unused(0)
        self._reject(ops, reason='result_shape_mismatch')

    def test_unknown_byte_is_not_a_call_terminator(self):
        op = instruction(2, 199, unused(1), unused(0), var(0, 1), 2)
        self.assertFalse(is_call_terminator(op))

    def test_decoder_refuses_when_the_symbol_table_is_missing(self):
        streams = decompress_encoded(LINKS, DICTIONARY.read_bytes())
        parsed = parse_binary(streams[0][1])
        group = parsed['main']
        for op in group['opcodes']:
            op['decoded_opcode'] = choose_opcode(op, MAPPING)
        cvs = {v['index']: bytes.fromhex(v['name_hex']) for v in group['compiled_vars']}
        decoder = Decoder(group['opcodes'], cvs, MAPPING, symbols=[], callees={})
        with self.assertRaises(Unsupported) as caught:
            decoder.run(0, len(group['opcodes']) - 1)
        self.assertIn('Encoder call rejected', str(caught.exception))

    def test_tampered_symbol_index_makes_the_whole_file_fail_closed(self):
        import tempfile
        buf, raw, offset = raw_stream(LINKS)
        parsed = parse_binary(raw)
        terminator_index = next(op['index'] for op in parsed['main']['opcodes']
                                if is_call_terminator(op))
        instruction_offset = parsed['main']['opcodes'][terminator_index]['offset']
        tampered = tamper_symbol_index(raw, instruction_offset, '9')
        with tempfile.TemporaryDirectory() as folder:
            target = write_tampered(Path(folder), tampered, buf[:offset])
            result = restore_result(target, DICTIONARY, OPCODE_MAP)
            self.assertEqual(result.status, 'unsupported')
            self.assertIsNone(result.code)
            self.assertIn('Encoder call rejected', result.audit['failure']['message'])


if __name__ == '__main__':
    unittest.main()
