"""Short-circuit joins whose term contains a call, and their refusals.

A comparison operand may be the result of a call.  The call is then decoded
as one closed segment and inlined into the folded condition, which changes
when the call runs.  The decoder therefore accepts it only when the call
lives in the short-circuit block itself and no statement of that block is
emitted after the call.
"""
from __future__ import annotations

import json
import sys
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from zend_decompiler.assets import DICTIONARY, OPCODE_MAP
from zend_decompiler.calibrate import choose_opcode
from zend_decompiler.crossblock import call_range, join_proofs
from zend_decompiler.engine import restore_result
from zend_decompiler.prefix_restore import Unsupported
from zend_decompiler.serial_parser import Reader, decompress_encoded, parse_binary
from zend_decompiler.structure import StructureError, build_graph

MAPPING = json.loads(OPCODE_MAP.read_text(encoding='utf-8'))


def group_of(parsed: dict, name: str) -> dict:
    for function in parsed['functions']:
        if bytes.fromhex(function['name_hex']).decode('cp1251') == name:
            return function
    raise AssertionError('no group ' + name)


def prepared(parsed: dict, name: str):
    group = group_of(parsed, name)
    for op in group['opcodes']:
        op['decoded_opcode'] = choose_opcode(op, MAPPING)
    cvs = {v['index']: bytes.fromhex(v['name_hex']) for v in group['compiled_vars']}
    return group, cvs


class CallTermProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        streams = decompress_encoded(ROOT / 'sample_inputs' / 'fun_all.php',
                                     DICTIONARY.read_bytes())
        cls.parsed = parse_binary(streams[0][1])

    def test_call_result_may_be_a_comparison_operand(self):
        group, cvs = prepared(self.parsed, 'out_link')
        proofs = join_proofs(group['opcodes'], cvs, MAPPING)
        self.assertIn(16, proofs)
        proof = proofs[16]
        self.assertEqual(proof['mode'], 'AND')
        self.assertEqual(proof['call_sites'],
                         [{'index': 11, 'first': 7, 'last': 11}])
        self.assertEqual(
            proof['expression'],
            "((strstr($REQUEST_URI, 'htm') == '') && ($old_search != 'y'))")
        # The call instructions are not part of the folded block coverage.
        self.assertEqual(proof['source_indices'], [12, 13, 14, 15, 16])

    def test_call_range_starts_at_the_initializer(self):
        group, cvs = prepared(self.parsed, 'out_link')
        names = {index: MAPPING['names'].get(str(choose_opcode(op, MAPPING)))
                 for index, op in enumerate(group['opcodes'])}
        first, last = call_range(group['opcodes'], lambda i: names[i], 11)
        self.assertEqual((first, last), (7, 11))
        self.assertEqual(names[first], 'INIT_FCALL_BY_NAME')
        self.assertEqual(names[last], 'DO_FCALL_BY_NAME')

    def test_a_call_without_an_initializer_is_refused(self):
        group, cvs = prepared(self.parsed, 'out_link')
        names = {index: MAPPING['names'].get(str(choose_opcode(op, MAPPING)))
                 for index, op in enumerate(group['opcodes'])}
        with self.assertRaises(Unsupported):
            call_range(group['opcodes'], lambda i: names[i], 3)

    def test_proof_is_refused_when_the_call_result_is_not_the_operand(self):
        group, cvs = prepared(self.parsed, 'out_link')
        ops = group['opcodes']
        # Break the slot of the call result so it no longer matches the
        # operand of the comparison.
        original = ops[11]['result']
        try:
            ops[11]['result'] = {'type': 4, 'word0': 7, 'word1': 0}
            proofs = join_proofs(ops, cvs, MAPPING)
            self.assertNotIn(16, proofs)
        finally:
            ops[11]['result'] = original

    def test_existing_pure_proofs_are_unchanged(self):
        group, cvs = prepared(self.parsed, 'currency_type')
        proofs = join_proofs(group['opcodes'], cvs, MAPPING)
        self.assertIn(9, proofs)
        self.assertEqual(proofs[9]['call_sites'], [])
        self.assertEqual(proofs[9]['expression'],
                         "(($CurTypeID[$text_key] == 0) || ($CurTypeID[$text_key] == ''))")


class FoldedCallSafetyTests(unittest.TestCase):
    """The folded condition may only carry a call that stays in place."""

    @staticmethod
    def blocks(statements, sources, lead_branch, lead_successors):
        return [{'id': 'B000', 'first': 0, 'last': 3, 'statements': statements,
                 'statement_sources': sources, 'branch': lead_branch,
                 'successors': lead_successors, 'predecessors': []},
                {'id': 'B005', 'first': 5, 'last': 5, 'statements': [],
                 'statement_sources': [],
                 'branch': {'opcode': 'JMPZ', 'condition': '(a && b)', 'target': 0},
                 'successors': [{'block': 'B009', 'kind': 'zero',
                                  'target_instruction': 9}],
                 'predecessors': []},
                {'id': 'B009', 'first': 9, 'last': 9, 'statements': ['return NULL;'],
                 'statement_sources': [9], 'branch': None, 'successors': [],
                 'predecessors': []}]

    def _proof(self, call_index=1):
        return {'join_index': 5, 'slot': [0, 0], 'mode': 'AND', 'expression': '(a && b)',
                'expression_hex': '(a && b)'.encode('cp1251').hex(),
                'comparison_count': 2, 'source_indices': [2, 3, 4, 5],
                'shortcut_indices': [3], 'call_sites': [{'index': call_index,
                                                         'first': call_index,
                                                         'last': call_index}],
                'fallthrough': 6, 'branch_target': 0, 'conditional_opcode': 'JMPZ'}

    def _data(self, statements, sources):
        lead_branch = {'opcode': 'JMPZ_EX', 'condition': '(a && b)', 'target': 5}
        lead_successors = [{'block': 'B005', 'kind': 'zero', 'target_instruction': 5}]
        blocks = self.blocks(statements, sources, lead_branch, lead_successors)
        return {'source': 'x', 'total': 6, 'blocks': blocks,
                'proven_short_circuit_joins': [self._proof()]}

    def test_statement_before_the_call_is_allowed(self):
        kept, graph, folded, removed = build_graph(self._data(['global $a;'], [0]))
        self.assertEqual(len(folded), 1)
        self.assertEqual(folded[0]['condition'], '(a && b)')

    def test_statement_after_the_call_is_refused(self):
        with self.assertRaises(StructureError):
            build_graph(self._data(['global $a;'], [2]))

    def test_call_outside_the_short_circuit_block_is_refused(self):
        data = self._data([], [])
        data['proven_short_circuit_joins'][0]['call_sites'][0]['index'] = 4
        with self.assertRaises(StructureError):
            build_graph(data)


class ExactFailureDiagnosticTests(unittest.TestCase):
    """A tampered input must still be pinpointed by the failure audit."""

    @staticmethod
    def find_stream_offset(buf: bytes, dictionary: bytes) -> int:
        checksum = zlib.adler32(dictionary)
        for index in range(len(buf) - 6):
            cmf, flg = buf[index:index + 2]
            if (cmf & 15) != 8 or (cmf >> 4) > 7 or ((cmf << 8) + flg) % 31 != 0 or not (flg & 0x20):
                continue
            if int.from_bytes(buf[index + 2:index + 6], 'big') == checksum:
                return index
        raise AssertionError('no zlib stream with the project dictionary')

    def test_unmapped_instruction_is_reported_with_its_index(self):
        source = ROOT / 'sample_inputs' / 'fun_all.php'
        buf = source.read_bytes()
        offset = self.find_stream_offset(buf, DICTIONARY.read_bytes())
        raw = decompress_encoded(source, DICTIONARY.read_bytes())[0][1]
        parsed = parse_binary(raw)
        group = group_of(parsed, 'out_price')
        # out_price #63/#64 are FE_RESET/FE_FETCH.  Unmapping both leaves the
        # control flow modellable and makes the decoder refuse at the first
        # of them, with an exact instruction index.
        tampered = raw
        for index, byte in ((63, 97), (64, 97)):
            position = group['opcodes'][index]['offset']
            tampered = tampered[:position] + bytes([byte]) + tampered[position + 1:]
        compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED,
                                      zlib.MAX_WBITS, zlib.DEF_MEM_LEVEL,
                                      zlib.Z_DEFAULT_STRATEGY, zdict=DICTIONARY.read_bytes())
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'tampered.php'
            target.write_bytes(buf[:offset] + compressor.compress(tampered) + compressor.flush())
            result = restore_result(target, DICTIONARY, OPCODE_MAP)
            self.assertEqual(result.status, 'unsupported')
            self.assertIsNone(result.code)
            failure = result.audit['failure']
            self.assertEqual(failure['opcode_index'], 63)
            self.assertEqual(failure['unknown_opcodes'], [63, 64, 65])
            self.assertEqual(failure['index_precision'], 'exact_unknown_opcode_indices')
            self.assertEqual(failure['block_window']['group'], 'out_price')
            self.assertEqual(failure['block_window']['index'], 63)


if __name__ == '__main__':
    unittest.main()
