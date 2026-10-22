"""Terminal blocks of the structured graph.

`exit` ends a PHP 5.2 script without a return, so a block whose last statement
is a bare `exit;` is a valid terminal.  Any other status form stays unproven,
because the emitter does not model `exit(<status>);` yet.
"""
from __future__ import annotations

import unittest

from zend_decompiler.structure import StructureError, build_graph


def data(statement):
    return {'source': 'x', 'total': 1,
            'blocks': [{'id': 'B000', 'first': 0, 'last': 0,
                        'statements': [statement], 'statement_sources': [0],
                        'branch': None, 'successors': [], 'predecessors': []}],
            'proven_short_circuit_joins': []}


class TerminalStatementTests(unittest.TestCase):
    def test_a_bare_exit_is_a_terminal_block(self):
        kept, _graph, _folded, _removed = build_graph(data('exit;'))
        self.assertIn('B000', kept)

    def test_an_exit_with_a_status_is_not_proven(self):
        with self.assertRaisesRegex(StructureError, 'Unproven terminal block'):
            build_graph(data('exit(1);'))

    def test_a_return_is_still_a_terminal_block(self):
        kept, _graph, _folded, _removed = build_graph(data('return NULL;'))
        self.assertIn('B000', kept)


if __name__ == '__main__':
    unittest.main()
