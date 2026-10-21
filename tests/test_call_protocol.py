"""Native PHP 5.2 positional direct-call protocol: positive and negative cases."""
import unittest
from zend_decompiler.call_protocol import CallProtocolError, DirectCallBuffer


class DirectCallProtocolTests(unittest.TestCase):
    def test_zero_argument_direct_call(self):
        q = DirectCallBuffer()
        self.assertEqual(q.finish(0), [])
        q.require_empty()

    def test_ordered_arguments_round_trip(self):
        q = DirectCallBuffer()
        q.push(1, b'$x')
        q.push(2, b"'a'")
        self.assertEqual(q.finish(2), [b'$x', b"'a'"])
        q.require_empty()

    def test_buffer_can_be_reused_without_leaking_args(self):
        q = DirectCallBuffer()
        q.push(1, b'1')
        q.finish(1)
        q.push(1, b'2')
        self.assertEqual(q.finish(1), [b'2'])

    def test_gap_in_positions_is_rejected(self):
        q = DirectCallBuffer()
        with self.assertRaisesRegex(CallProtocolError, 'argument order mismatch'):
            q.push(2, b'1')

    def test_duplicate_argument_is_rejected(self):
        q = DirectCallBuffer()
        q.push(1, b'1')
        with self.assertRaisesRegex(CallProtocolError, 'argument order mismatch'):
            q.push(1, b'2')

    def test_missing_argument_is_rejected(self):
        q = DirectCallBuffer()
        q.push(1, b'1')
        with self.assertRaisesRegex(CallProtocolError, 'argument count mismatch'):
            q.finish(2)

    def test_negative_and_non_integer_arity_are_rejected(self):
        for n in (-1, 1.0, '0', True):
            with self.subTest(n=n), self.assertRaises(CallProtocolError):
                DirectCallBuffer().finish(n)

    def test_unpaired_send_fails_at_boundary(self):
        q = DirectCallBuffer()
        q.push(1, b'1')
        with self.assertRaisesRegex(CallProtocolError, 'block boundary'):
            q.require_empty()
