"""Fail-closed argument protocol for PHP 5.2 direct DO_FCALL.

Native PHP 5.2 may emit SEND_* / DO_FCALL without INIT_FCALL_BY_NAME.
Only positional, ordered arguments are admitted; this is not evidence for
an uncertain serialized-to-native opcode mapping.
"""
from __future__ import annotations


class CallProtocolError(ValueError):
    """Unsupported or inconsistent function-call argument protocol."""


class DirectCallBuffer:
    """Collect SEND operands for a direct named call within one basic block."""

    def __init__(self) -> None:
        self._arguments: list[bytes] = []

    def push(self, position: int, expression: bytes) -> None:
        if type(position) is not int or position != len(self._arguments) + 1:
            raise CallProtocolError(
                f'Direct-call argument order mismatch: expected {len(self._arguments) + 1}, got {position!r}'
            )
        self._arguments.append(expression)

    def finish(self, arity: int) -> list[bytes]:
        if type(arity) is not int or arity < 0 or arity != len(self._arguments):
            raise CallProtocolError(
                f'Direct-call argument count mismatch: sent {len(self._arguments)}, expected {arity!r}'
            )
        arguments = self._arguments
        self._arguments = []
        return arguments

    def require_empty(self) -> None:
        if self._arguments:
            raise CallProtocolError('Unfinished direct-call SEND sequence at block boundary')
