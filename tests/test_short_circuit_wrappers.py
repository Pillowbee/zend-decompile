"""Boolean wrappers inside a proven short-circuit term.

A comparison may be wrapped in BOOL and BOOL_NOT before it feeds a join.  The
proof keeps the exact decoder rendering in `rendered_term` and records every
wrapper slot, so a block that contains the join can be decoded with the same
values.  A negation must stay in the composite condition: dropping it would
generate a different program.
"""
from __future__ import annotations

import unittest

from zend_decompiler.crossblock import join_proofs
from zend_decompiler.structure import StructureError, build_graph

IS_EQUAL = 17
BOOL_NOT = 13
BOOL = 52
JMPZ = 43
JMPZ_EX = 46


def unused(value=0, marker=1):
    return {'type': 8, 'word0': value, 'word1': marker}


def temporary(n=0):
    return {'type': 2, 'word0': n, 'word1': 0}


def compiled_variable(n=0):
    return {'type': 16, 'word0': n, 'word1': 0}


def integer(n):
    return {'type': 1, 'constant': {'kind': 'integer', 'value': n}}


def ins(index, opcode, *, op1=None, op2=None, result=None):
    return {'index': index, 'encoded_opcode': 100 + index, 'line': index + 1,
            'extended_value': 0,
            'op1': unused() if op1 is None else op1,
            'op2': unused() if op2 is None else op2,
            'result': unused() if result is None else result,
            '_native': opcode}


NAMES = {IS_EQUAL: 'IS_EQUAL', BOOL_NOT: 'BOOL_NOT', BOOL: 'BOOL',
         JMPZ: 'JMPZ', JMPZ_EX: 'JMPZ_EX'}
CVS = {0: b'a', 1: b'b'}


def prove(ops):
    mapping = {'names': {str(code): name for code, name in NAMES.items()},
               'opcodes': {f"{op['index'] % 8}:{op['encoded_opcode']}": op['_native']
                           for op in ops}}
    return join_proofs(ops, CVS, mapping)


def with_last_term(*wrappers):
    """Comparison on $b == 2, wrapped by `wrappers` from the inside out."""
    ops = [ins(0, IS_EQUAL, op1=compiled_variable(0), op2=integer(1),
               result=temporary(0)),
           ins(1, JMPZ_EX, op1=temporary(0), result=temporary(0)),
           ins(2, IS_EQUAL, op1=compiled_variable(1), op2=integer(2),
               result=temporary(2))]
    slot = 2
    for opcode in wrappers:
        slot += 1
        ops.append(ins(len(ops), opcode, op1=temporary(slot - 1),
                       result=temporary(slot)))
    join = len(ops)
    ops.append(ins(join, JMPZ, op1=temporary(slot), op2=unused(9, 1)))
    # The short circuit jumps to the join, whose position depends on the
    # number of wrappers.
    ops[1]['op2'] = unused(join, 1)
    return ops


class WrapperProofTests(unittest.TestCase):
    def test_negation_stays_in_the_composite_condition(self):
        proof = prove(with_last_term(BOOL_NOT))[4]
        self.assertEqual(proof['expression'],
                         '(($a == 1) && !($b == 2))')
        self.assertEqual(proof['rendered_term'], '(!($b == 2))')
        self.assertEqual(
            proof['term_slots'],
            [{'slot': [2, 2, 0], 'value_hex': b'($b == 2)'.hex()},
             {'slot': [2, 3, 0], 'value_hex': b'(!($b == 2))'.hex()}])

    def test_boolean_conversion_is_the_identity_in_a_condition(self):
        proof = prove(with_last_term(BOOL))[4]
        self.assertEqual(proof['expression'],
                         '(($a == 1) && ($b == 2))')
        self.assertEqual(proof['rendered_term'], '((bool) ($b == 2))')

    def test_two_negations_cancel_but_are_rendered_exactly(self):
        proof = prove(with_last_term(BOOL_NOT, BOOL_NOT))[5]
        self.assertEqual(proof['expression'],
                         '(($a == 1) && ($b == 2))')
        self.assertEqual(proof['rendered_term'], '(!(!($b == 2)))')

    def test_a_wrapper_in_a_foreign_slot_breaks_the_proof(self):
        ops = with_last_term(BOOL_NOT)
        ops[3]['result'] = temporary(9)
        self.assertNotIn(4, prove(ops))


BLOCKS = [
    {'id': 'B000', 'first': 0, 'last': 3, 'statements': [],
     'statement_sources': [], 'branch': {'opcode': 'JMPZ_EX',
                                         'condition': '($a == 1)', 'target': 5},
     'successors': [{'block': 'B005', 'kind': 'zero',
                     'target_instruction': 5}],
     'predecessors': []},
    {'id': 'B005', 'first': 5, 'last': 5, 'statements': [],
     'statement_sources': [], 'branch': {'opcode': 'JMPZ',
                                         'condition': '', 'target': 9},
     'successors': [{'block': 'B009', 'kind': 'zero',
                     'target_instruction': 9}],
     'predecessors': []},
    {'id': 'B009', 'first': 9, 'last': 9, 'statements': ['return NULL;'],
     'statement_sources': [9], 'branch': None, 'successors': [],
     'predecessors': []},
]


def graph_data(join_condition):
    proof = {'join_index': 5, 'slot': [2, 0, 0], 'mode': 'AND',
             'expression': '(($a == 1) && !($b == 2))',
             'expression_hex': '(($a == 1) && !($b == 2))'.encode('cp1251').hex(),
             'rendered_term': '(!($b == 2))',
             'term_slots': [{'slot': [2, 2, 0],
                             'value_hex': b'($b == 2)'.hex()},
                            {'slot': [2, 3, 0],
                             'value_hex': b'(!($b == 2))'.hex()}],
             'comparison_count': 2, 'source_indices': [2, 3, 4, 5],
             'shortcut_indices': [3], 'call_sites': [], 'fallthrough': 6,
             'branch_target': 9, 'conditional_opcode': 'JMPZ'}
    blocks = [dict(b) for b in BLOCKS]
    blocks[1]['branch'] = dict(blocks[1]['branch'], condition=join_condition)
    return {'source': 'x', 'total': 10, 'blocks': blocks,
            'proven_short_circuit_joins': [proof]}


class WrapperFoldTests(unittest.TestCase):
    def test_the_proven_composite_replaces_the_lead_condition(self):
        kept, _graph, folded, _removed = build_graph(graph_data('(!($b == 2))'))
        self.assertEqual(folded[0]['condition'], '(($a == 1) && !($b == 2))')
        self.assertEqual(kept['B000']['branch']['condition'],
                         '(($a == 1) && !($b == 2))')

    def test_a_join_that_dropped_the_negation_is_refused(self):
        with self.assertRaisesRegex(StructureError, 'Proof and join disagree'):
            build_graph(graph_data('($b == 2)'))


if __name__ == '__main__':
    unittest.main()
