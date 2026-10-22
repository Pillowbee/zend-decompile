"""Encoder operand forms added for the remaining corpus gaps.

Every case is synthetic and decoded through the public Decoder; no protected
PHP stream is executed or copied.  The positive cases follow the saved PHP 5.2
handlers (`reference_headers_php52_candidate/zend_vm_def.h`): INIT_ARRAY and
ADD_ARRAY_ELEMENT carry the value in op1 and the offset in op2, EXIT uses an
unused operand for a bare exit, UNSET_VAR carries the variable name, and
FETCH_FUNC_ARG reads the name from its operand, so a compiled variable means a
variable variable.
"""
from __future__ import annotations

import unittest

from zend_decompiler.prefix_restore import Decoder, Unsupported, sym


def unused(value=0, marker=1):
    return {'type': 8, 'word0': value, 'word1': marker}


def temporary(n=0, kind=2):
    return {'type': kind, 'word0': n, 'word1': 0}


def compiled_variable(n=0):
    return {'type': 16, 'word0': n, 'word1': 0}


def integer(n):
    return {'type': 1, 'constant': {'kind': 'integer', 'value': n}}


def string(value):
    if isinstance(value, str):
        value = value.encode('cp1251')
    return {'type': 1, 'constant': {'kind': 'string', 'raw_hex': value.hex()}}


def null():
    return {'type': 1, 'constant': {'kind': 'null'}}


def ins(index, opcode, *, op1=None, op2=None, result=None, ext=0):
    return {'index': index, 'encoded_opcode': 100 + index, 'line': index + 1,
            'extended_value': ext,
            'op1': unused() if op1 is None else op1,
            'op2': unused() if op2 is None else op2,
            'result': unused() if result is None else result,
            '_native': opcode}


def decode(ops, names, cv_names=None):
    mapping = {
        'names': {str(code): name for code, name in names.items()},
        'opcodes': {f"{op['index'] % 8}:{op['encoded_opcode']}": op['_native']
                    for op in ops if op['_native'] is not None},
    }
    variables = {index: name for index, name in (cv_names or {}).items()}
    return Decoder(ops, variables, mapping).run(0, len(ops) - 1)


class ArrayLiteralTests(unittest.TestCase):
    NAMES = {71: 'INIT_ARRAY', 72: 'ADD_ARRAY_ELEMENT', 40: 'ECHO'}

    def test_keyed_and_appended_elements_keep_their_order(self):
        ops = [ins(0, 71, op1=integer(1), op2=string('a'), result=temporary()),
               ins(1, 72, op1=integer(2), op2=integer(0), result=temporary()),
               ins(2, 72, op1=integer(3), result=temporary()),
               ins(3, 40, op1=temporary())]
        segment = decode(ops, self.NAMES)
        self.assertEqual(segment.statements,
                         [b"echo array('a' => 1, 0 => 2, 3);"])

    def test_empty_array_needs_no_value_and_no_offset(self):
        ops = [ins(0, 71, result=temporary()),
               ins(1, 40, op1=temporary())]
        self.assertEqual(decode(ops, self.NAMES).statements,
                         [b'echo array();'])

    def test_empty_array_with_an_offset_is_refused(self):
        ops = [ins(0, 71, op2=integer(0), result=temporary())]
        with self.assertRaisesRegex(Unsupported, 'Empty INIT_ARRAY with an offset'):
            decode(ops, self.NAMES)

    def test_by_reference_element_is_refused_on_init(self):
        ops = [ins(0, 71, op1=integer(1), result=temporary(), ext=1)]
        with self.assertRaisesRegex(Unsupported,
                                    'Array element by reference unsupported'):
            decode(ops, self.NAMES)

    def test_by_reference_element_is_refused_on_append(self):
        ops = [ins(0, 71, op1=integer(1), op2=string('a'), result=temporary()),
               ins(1, 72, op1=integer(1), result=temporary(), ext=1)]
        with self.assertRaisesRegex(Unsupported,
                                    'Array element by reference unsupported'):
            decode(ops, self.NAMES)

    def test_non_constant_offset_is_refused(self):
        ops = [ins(0, 71, op1=integer(1), op2=temporary(3), result=temporary())]
        with self.assertRaisesRegex(Unsupported, 'Unsupported array offset'):
            decode(ops, self.NAMES)

    def test_null_offset_is_refused(self):
        ops = [ins(0, 71, op1=integer(1), op2=null(), result=temporary())]
        with self.assertRaisesRegex(Unsupported, 'Unsupported array offset kind'):
            decode(ops, self.NAMES)

    def test_append_without_a_matching_init_is_refused(self):
        ops = [ins(0, 72, op1=integer(1), result=temporary())]
        with self.assertRaisesRegex(Unsupported, 'Unmatched ADD_ARRAY_ELEMENT'):
            decode(ops, self.NAMES)


class ExitAndUnsetTests(unittest.TestCase):
    def test_bare_exit(self):
        ops = [ins(0, 79)]
        self.assertEqual(decode(ops, {79: 'EXIT'}).statements, [b'exit;'])

    def test_exit_with_an_integer_status(self):
        ops = [ins(0, 79, op1=integer(0))]
        self.assertEqual(decode(ops, {79: 'EXIT'}).statements, [b'exit(0);'])

    def test_exit_with_a_string_status(self):
        ops = [ins(0, 79, op1=string('bye'))]
        self.assertEqual(decode(ops, {79: 'EXIT'}).statements, [b"exit('bye');"])

    def test_exit_with_a_temporary_is_refused(self):
        ops = [ins(0, 79, op1=temporary())]
        with self.assertRaisesRegex(Unsupported, 'Unsupported EXIT operand'):
            decode(ops, {79: 'EXIT'})

    def test_exit_with_a_compiled_variable_is_refused(self):
        ops = [ins(0, 79, op1=compiled_variable())]
        with self.assertRaisesRegex(Unsupported, 'Unsupported EXIT operand'):
            decode(ops, {79: 'EXIT'}, {0: b'x'})

    def test_unset_names_the_variable(self):
        ops = [ins(0, 74, op1=string('gone'))]
        self.assertEqual(decode(ops, {74: 'UNSET_VAR'}).statements,
                         [b'unset($gone);'])

    def test_unset_accepts_a_cp1251_identifier(self):
        name = 'данные'.encode('cp1251')
        ops = [ins(0, 74, op1=string(name))]
        self.assertEqual(decode(ops, {74: 'UNSET_VAR'}).statements,
                         [b'unset($' + name + b');'])

    def test_unset_with_a_non_constant_operand_is_refused(self):
        ops = [ins(0, 74, op1=temporary())]
        with self.assertRaisesRegex(Unsupported, 'Unexpected UNSET_VAR operand'):
            decode(ops, {74: 'UNSET_VAR'})

    def test_unset_with_a_non_identifier_is_refused(self):
        ops = [ins(0, 74, op1=string(b'not a name'))]
        with self.assertRaisesRegex(Unsupported, 'Non-simple PHP identifier'):
            decode(ops, {74: 'UNSET_VAR'})


class DynamicArgumentNameTests(unittest.TestCase):
    NAMES = {92: 'FETCH_FUNC_ARG', 40: 'ECHO'}

    def test_constant_operand_names_the_argument(self):
        ops = [ins(0, 92, op1=string('x'), result=temporary(0, kind=4)),
               ins(1, 40, op1=temporary(0, kind=4))]
        self.assertEqual(decode(ops, self.NAMES).statements, [b'echo $x;'])

    def test_compiled_variable_operand_is_a_variable_variable(self):
        ops = [ins(0, 92, op1=compiled_variable(0), result=temporary(0, kind=4)),
               ins(1, 40, op1=temporary(0, kind=4))]
        self.assertEqual(decode(ops, self.NAMES, {0: b'name_field'}).statements,
                         [b'echo ${$name_field};'])

    def test_compiled_variable_operand_keeps_cp1251_name(self):
        name = 'имя'.encode('cp1251')
        ops = [ins(0, 92, op1=compiled_variable(0), result=temporary(0, kind=4)),
               ins(1, 40, op1=temporary(0, kind=4))]
        self.assertEqual(decode(ops, self.NAMES, {0: name}).statements,
                         [b'echo ${$' + name + b'};'])

    def test_temporary_operand_is_refused(self):
        ops = [ins(0, 92, op1=temporary(), result=temporary(0, kind=4))]
        with self.assertRaisesRegex(Unsupported,
                                    'Unsupported FETCH_FUNC_ARG operand'):
            decode(ops, self.NAMES)


class IdentifierTests(unittest.TestCase):
    def test_cp1251_identifier_is_accepted(self):
        name = b'\xe0r\xe5\xe0_table'
        self.assertEqual(sym(name), name)

    def test_identifier_may_not_start_with_a_digit_or_contain_spaces(self):
        for name in (b'', b'1x', b'a b', b'a-b', b'a.b'):
            with self.assertRaisesRegex(Unsupported, 'Non-simple PHP identifier'):
                sym(name)


if __name__ == '__main__':
    unittest.main()
