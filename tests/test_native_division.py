"""Native PHP 5.2 DIV expression restoration; only synthetic data, no PHP execution."""
import unittest
from zend_decompiler.prefix_restore import Decoder, Unsupported


def unused():
    return {'type': 8, 'word0': 0, 'word1': 1}


def temporary(n=0):
    return {'type': 2, 'word0': n, 'word1': 0}


def variable(n=0):
    return {'type': 16, 'word0': n, 'word1': 0}


def integer(n):
    return {'type': 1, 'constant': {'kind': 'integer', 'value': n}}


def ins(i, code, a=None, b=None, result=None):
    return {'index': i, 'encoded_opcode': 170 + i, 'line': i+1,
            'extended_value': 0, 'op1': unused() if a is None else a,
            'op2': unused() if b is None else b,
            'result': unused() if result is None else result, 'native': code}


def decode(ops):
    # Intentionally omit name 4: the saved map has an inferred opcode ID 4 but
    # lacks its native label. The fallback must be header-grounded, not guessed.
    mapping={'names': {'3': 'MUL', '40':'ECHO'},
             'opcodes': {f"{o['index']%8}:{o['encoded_opcode']}":o['native'] for o in ops}}
    return Decoder(ops,{0:b'amount'},mapping).run(0,len(ops)-1)


class NativeDivisionTests(unittest.TestCase):
    def test_division_preserves_parentheses(self):
        ops=[ins(0,4,variable(),integer(2),temporary()),
             ins(1,40,temporary())]
        self.assertEqual(decode(ops).statements,[b'echo ($amount / 2);'])

    def test_division_accepts_previously_defined_temporary(self):
        ops=[ins(0,3,integer(2),integer(3),temporary()),
             ins(1,4,temporary(),integer(5),temporary(1)),
             ins(2,40,temporary(1))]
        self.assertEqual(decode(ops).statements,[b'echo ((2 * 3) / 5);'])

    def test_division_with_unknown_producer_is_rejected(self):
        with self.assertRaisesRegex(Unsupported,'Unresolved temporary'):
            decode([ins(0,4,temporary(),integer(2),temporary(1))])
