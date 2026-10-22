"""The encoder level foreach layer.

Two instructions of a foreach have no established native opcode number:

* the binding of the element, which the optimizer replaces with a NOP in the
  native op_array, and
* the fetch of the element in files where the optimizer rewrites the whole
  foreach and gives the instruction a generic handler, so the handler address
  does not identify it.

Both are therefore recognised by their data flow and their position inside
the construct, never by an opcode number.  The recognition is used only where
the empirical map has no entry for the position.
"""
from __future__ import annotations

from .calibrate import choose_opcode

FE_RESET = 77
FE_FETCH = 78


def _opcode(op: dict, mapping: dict | None) -> int | None:
    if op.get('decoded_opcode') is not None:
        return op['decoded_opcode']
    if mapping is None:
        return None
    return choose_opcode(op, mapping)


def _slot(node: dict):
    if node.get('type') not in (2, 4):
        return None
    return (node['type'], node.get('word0', 0), node.get('word1', 0))


def foreach_fetches(ops: list, mapping: dict | None = None) -> set:
    """Indices of the instructions that fetch the element of a foreach.

    A fetch follows the reset of the same foreach, it reads the iterator of
    that reset and it produces a temporary.
    """
    fetches = set()
    for index in range(1, len(ops)):
        op = ops[index]
        if _opcode(op, mapping) is not None:
            continue                    # the empirical map knows the instruction
        previous = ops[index - 1]
        if _opcode(previous, mapping) != FE_RESET:
            continue
        if op['op1'].get('type') not in (2, 4):
            continue
        if op['result'].get('type') != 2:
            continue
        if _slot(op['op1']) != _slot(previous['result']):
            continue
        fetches.add(op['index'])
    return fetches


def foreach_markers(ops: list, mapping: dict | None = None) -> set:
    """Indices of the instructions that bind the element of a foreach.

    A binding follows the fetch of the same foreach, it reads the element
    that the fetch produced and it produces a writable container.
    """
    markers = set()
    fetches = foreach_fetches(ops, mapping)
    for index, op in enumerate(ops):
        opcode = _opcode(op, mapping)
        if opcode != FE_FETCH and index not in fetches:
            continue
        if index + 1 >= len(ops):
            continue
        following = ops[index + 1]
        if following['op1'].get('type') not in (2, 4):
            continue
        if following['result'].get('type') != 4:
            continue
        if _slot(following['op1']) != _slot(op['result']):
            continue
        markers.add(following['index'])
    return markers
