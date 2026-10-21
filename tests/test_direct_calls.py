"""Synthetic Decoder regressions for PHP 5.2 direct calls.

Never executes protected PHP; requires neither PHP nor a compile-only probe.
"""
import unittest
from zend_decompiler.prefix_restore import Decoder, Unsupported


def unused(value=0, marker=0):
    return {'type': 8, 'word0': value, 'word1': marker}


def temporary(n=0):
    return {'type': 4, 'word0': n, 'word1': 0}


def variable(n=0):
    return {'type': 16, 'word0': n, 'word1': 0}


def integer(n):
    return {'type': 1, 'constant': {'kind': 'integer', 'value': n}}


def string(value):
    return {'type': 1, 'constant': {'kind': 'string', 'raw_hex': value.encode('ascii').hex()}}


def ins(index, opcode, *, op1=None, op2=None, result=None, arity=0):
    return {'index': index, 'encoded_opcode': 100 + index, 'line': index+1,
            'extended_value': arity,
            'op1': unused() if op1 is None else op1,
            'op2': unused() if op2 is None else op2,
            'result': unused() if result is None else result,
            '_native': opcode}


def decode(ops):
    names={59:'INIT_FCALL_BY_NAME',60:'DO_FCALL',61:'DO_FCALL_BY_NAME',
           65:'SEND_VAL',66:'SEND_VAR',40:'ECHO',62:'RETURN'}
    mapping={'names':{str(code):name for code,name in names.items()},
             'opcodes':{f"{op['index']%8}:{op['encoded_opcode']}":op['_native'] for op in ops}}
    return Decoder(ops,{0:b'x'},mapping).run(0,len(ops)-1)


class DirectFCallDecoderTests(unittest.TestCase):
    def test_native_send_val_do_fcall_echo(self):
        # corpus/compile_only_dumps/01_calls.log: SEND_VAL(65), DO_FCALL(60), argcount=1.
        ops=[ins(0,65,op1=integer(2),op2=unused(1)),
             ins(1,60,op1=string('f'),result=temporary(),arity=1),
             ins(2,40,op1=temporary())]
        self.assertEqual(decode(ops).statements,[b'echo f(2);'])

    def test_unconsumed_direct_call_is_emitted_once(self):
        ops=[ins(0,65,op1=integer(2),op2=unused(1)),
             ins(1,60,op1=string('f'),result=temporary(),arity=1)]
        self.assertEqual(decode(ops).statements,[b'f(2);'])

    def test_two_ordered_arguments(self):
        ops=[ins(0,66,op1=variable(),op2=unused(1)),
             ins(1,65,op1=integer(3),op2=unused(2)),
             ins(2,60,op1=string('f'),result=temporary(),arity=2),
             ins(3,40,op1=temporary())]
        self.assertEqual(decode(ops).statements,[b'echo f($x, 3);'])

    def test_direct_call_can_be_followed_by_another_call(self):
        ops=[ins(0,65,op1=integer(1),op2=unused(1)),
             ins(1,60,op1=string('f'),result=temporary(),arity=1),
             ins(2,65,op1=integer(2),op2=unused(1)),
             ins(3,60,op1=string('g'),result=temporary(1),arity=1)]
        self.assertEqual(decode(ops).statements,[b'f(1);',b'g(2);'])

    def test_legacy_initialized_call_is_unchanged(self):
        ops=[ins(0,59,op2=string('f')),
             ins(1,65,op1=integer(2),op2=unused(1)),
             ins(2,61,op1=string('f'),result=temporary(),arity=1),
             ins(3,40,op1=temporary())]
        self.assertEqual(decode(ops).statements,[b'echo f(2);'])

    def test_unfinished_direct_send_is_rejected(self):
        with self.assertRaisesRegex(Unsupported,'Unfinished direct-call SEND'):
            decode([ins(0,65,op1=integer(1),op2=unused(1))])

    def test_wrong_argument_count_is_rejected(self):
        with self.assertRaisesRegex(Unsupported,'argument count mismatch'):
            decode([ins(0,65,op1=integer(1),op2=unused(1)),
                    ins(1,60,op1=string('f'),result=temporary(),arity=2)])

    def test_argument_order_is_rejected(self):
        with self.assertRaisesRegex(Unsupported,'argument order mismatch'):
            decode([ins(0,65,op1=integer(1),op2=unused(2)),
                    ins(1,60,op1=string('f'),result=temporary(),arity=1)])

    def test_dynamic_callee_is_not_guessed(self):
        with self.assertRaisesRegex(Unsupported,'Expected literal string'):
            decode([ins(0,60,op1=variable(),result=temporary(),arity=0)])

    def test_unknown_direct_call_operand_is_rejected(self):
        with self.assertRaisesRegex(Unsupported,'Unsupported direct DO_FCALL operand2'):
            decode([ins(0,60,op1=string('f'),op2=unused(1),result=temporary(),arity=0)])

    def test_direct_call_cannot_steal_initialized_call_arguments(self):
        with self.assertRaisesRegex(Unsupported,'inside initialized call state'):
            decode([ins(0,59,op2=string('g')),
                    ins(1,65,op1=integer(1),op2=unused(1)),
                    ins(2,60,op1=string('f'),result=temporary(),arity=0)])
