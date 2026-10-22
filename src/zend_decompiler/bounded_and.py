"""Proofs for three bounded PHP 5.2 short-circuit AND layouts.

The layouts are selected by opcode sequence, never by a source filename.  A
truth-table walk checks the actual jump and temporary-slot behavior before a
condition is moved into one PHP expression.
"""
from __future__ import annotations

from itertools import product

from .calibrate import choose_opcode
from .cfg import cfg_for_group
from .prefix_restore import Decoder, Unsupported, spot
from .readonly_dataflow import read_definitions


SHAPES = (
    (('IS_NOT_EQUAL', 'JMPZ_EX', 'IS_NOT_EQUAL', 'JMPZ_EX',
      'IS_NOT_EQUAL', 'BOOL', 'BOOL', 'JMPZ_EX', 'IS_NOT_EQUAL',
      'JMPZ_EX', 'IS_NOT_EQUAL', 'BOOL', 'BOOL', 'JMPZ'),
     (0, 2, 4, 8, 10), (1, 3, 7, 9), (6, 12)),
    (('IS_NOT_EQUAL', 'JMPZ_EX', 'IS_NOT_EQUAL', 'BOOL',
      'JMPZ_EX', 'BOOL', 'JMPZ'),
     (0, 2, 5), (1, 4), ()),
    (('INIT_FCALL_BY_NAME', 'CONCAT', 'SEND_VAL', 'DO_FCALL_BY_NAME',
      'JMPZ_EX', 'IS_NOT_EQUAL', 'BOOL', 'JMPZ_EX',
      'IS_NOT_EQUAL', 'BOOL', 'JMPZ'),
     (3, 5, 8), (4, 7), ()),
)


def _proof(ops, cv, mapping, evidence, join, shape):
    names, term_offsets, shortcut_offsets, merge_offsets = shape
    start = join - len(names) + 1
    if start < 0:
        raise Unsupported('Short condition begins before group')
    segment = ops[start:join + 1]
    decoder = Decoder(ops, cv, mapping)
    if tuple(decoder.kind(op) for op in segment) != names:
        raise Unsupported('Different short condition')
    for op in segment:
        key = f'{op["index"] % 8}:{op["encoded_opcode"]}'
        record = evidence.get(key)
        kind = decoder.kind(op)
        expected_extended = (61 if kind == 'SEND_VAL' else
                             1 if kind == 'DO_FCALL_BY_NAME' else 0)
        if (record is None or record.get('status') != 'confirmed' or
                record.get('opcode') != choose_opcode(op, mapping) or
                mapping['opcodes'].get(key) != record['opcode'] or
                op['extended_value'] != expected_extended):
            raise Unsupported('Condition has an unconfirmed opcode')
    terms = []
    call_first = names[0] == 'INIT_FCALL_BY_NAME'
    for offset in term_offsets:
        op = segment[offset]
        if offset == term_offsets[0] and call_first:
            # The whole call, including its argument expression, is one
            # closed interval; its result is evaluated only on this path.
            local = Decoder(ops, cv, mapping)
            local.run(start, start + offset)
            value = local.defs.get(spot(op['result']))
            if value is None or local.pending_calls != {spot(op['result']): 0}:
                raise Unsupported('Call term is not closed')
        elif decoder.kind(op) == 'BOOL':
            if op['op1']['type'] != 16:
                raise Unsupported('Last term is not a compiled variable')
            value = decoder.val(op['op1'])
        else:
            if (op['op1']['type'] not in (1, 16) or
                    op['op2']['type'] not in (1, 16) or
                    op['result']['type'] != 2):
                raise Unsupported('Comparison is not pure CV/constant')
            local = Decoder(ops, cv, mapping)
            local.run(start + offset, start + offset)
            value = local.defs[spot(op['result'])]
        terms.append(value)
    checked = [dict(op, decoded_opcode=choose_opcode(op, mapping)) for op in ops]
    group = {'opcodes': checked, 'compiled_vars': [], 'loop_records': []}
    cfg = cfg_for_group('<bounded AND>', group)
    blocks = cfg['basic_blocks']
    lead = next((b for b in blocks if b['first'] <= start <= b['last']), None)
    tail = next((b for b in blocks if b['first'] == join), None)
    if lead is None or tail is None or not lead['reachable'] or not tail['reachable']:
        raise Unsupported('Short condition has no reachable CFG blocks')
    by_id = {b['id']: b for b in blocks}
    for block in blocks:
        if start < block['first'] <= join:
            if any(by_id[p]['last'] < start or by_id[p]['last'] >= join
                   for p in block['predecessors']):
                raise Unsupported('External entry into short condition')
    analysis = read_definitions(group, title='<bounded AND>')
    if analysis['status'] != 'analyzed_syntactically':
        raise Unsupported('No reaching-definition analysis')
    for use in analysis['temporary_uses']:
        definitions = set(use['reaching_definition_indices'])
        if definitions & set(range(start, join)):
            if not (start <= use['instruction_index'] <= join and
                    definitions <= set(range(start, join))):
                raise Unsupported('Condition temporary escapes its interval')
    term_at = {start + off: n for n, off in enumerate(term_offsets)}
    cuts = [start + off for off in shortcut_offsets]
    if any(segment[off]['op2']['type'] != 8 or
           segment[off]['op2']['word1'] != 1 for off in shortcut_offsets):
        raise Unsupported('Nonabsolute short-circuit jump')
    for values in product((False, True), repeat=len(terms)):
        slots = {}
        visited = []
        pc = start
        for _ in range(len(segment) + 1):
            if pc == join:
                final = ops[pc]
                first_false = next((i for i, value in enumerate(values)
                                    if not value), len(values) - 1)
                expected_visits = list(range(first_false + 1))
                if (spot(final['op1']) not in slots or
                        slots[spot(final['op1'])] != all(values) or
                        visited != expected_visits):
                    # The expected visited terms are the prefix through the
                    # first false term, or all terms if none is false.
                    raise Unsupported('Short-circuit truth table disagrees')
                break
            if not start <= pc < join:
                raise Unsupported('Condition escapes before its join')
            op = ops[pc]
            kind = decoder.kind(op)
            if pc in term_at:
                ordinal = term_at[pc]
                visited.append(ordinal)
                slots[spot(op['result'])] = values[ordinal]
            elif kind == 'BOOL':
                key = spot(op['op1'])
                if key not in slots:
                    raise Unsupported('BOOL reads an unproved slot')
                slots[spot(op['result'])] = slots[key]
            elif kind == 'JMPZ_EX':
                key = spot(op['op1'])
                if key not in slots:
                    raise Unsupported('Shortcut reads an unproved slot')
                value = slots[key]
                slots[spot(op['result'])] = value
                if not value:
                    pc = op['op2']['word0']
                    continue
            pc += 1
        else:
            raise Unsupported('Short condition does not reach its join')
    if len(cuts) < 2 or any(ops[i]['op2']['word0'] not in range(i + 1, join + 1)
                             for i in cuts):
        raise Unsupported('Unexpected short-circuit targets')
    expression = b'(' + b' && '.join(terms) + b')'
    seeds = []
    for off in merge_offsets:
        index = start + off
        preceding = next((i for i in reversed(cuts) if i < index and
                          ops[i]['op2']['word0'] == index), None)
        if preceding is None:
            raise Unsupported('BOOL merge lacks a shortcut')
        left = max(i for i, term_off in enumerate(term_offsets)
                   if start + term_off < preceding)
        if left + 1 >= len(terms):
            raise Unsupported('BOOL merge has no right term')
        inner = b'(' + terms[left] + b' && ' + terms[left + 1] + b')'
        seeds.append({'instruction_index': index,
                      'slot': list(spot(ops[index]['op1'])),
                      'value_hex': inner.hex()})
    final = ops[join]
    if final['op2']['type'] != 8 or final['op2']['word1'] != 1:
        raise Unsupported('Final condition has no absolute target')
    return {'join_index': join, 'slot': list(spot(final['op1'])),
            'mode': 'AND', 'expression_hex': expression.hex(),
            'expression': expression.decode('cp1251'),
            'comparison_count': len(terms),
            'source_indices': list(range(start, join + 1)),
            'shortcut_indices': cuts,
            'call_sites': ([{'first': start, 'last': start + term_offsets[0],
                            'index': start + term_offsets[0]}] if call_first else []),
            'term_slots': [], 'rendered_term': expression.decode('cp1251'),
            'fallthrough': join + 1, 'branch_target': final['op2']['word0'],
            'conditional_opcode': 'JMPZ', 'block_seeds': seeds,
            'nested': True, 'effectful_call_chain': call_first,
            'bounded_and_truth_table': True}


def bounded_and_proofs(ops, cv, mapping, evidence):
    result = {}
    for join, op in enumerate(ops):
        if mapping['names'].get(str(choose_opcode(op, mapping))) != 'JMPZ':
            continue
        for shape in SHAPES:
            try:
                result[join] = _proof(ops, cv, mapping, evidence, join, shape)
                break
            except (Unsupported, KeyError, ValueError, TypeError, IndexError):
                continue
    return result
