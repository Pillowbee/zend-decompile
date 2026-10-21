#!/usr/bin/env python3
"""Offline Zend 2002-era stream → basic-block CFG, conservative annotated IR.

This is NOT a universal PHP decompiler. Opcode IDs come from a supplied empirical
mapping and unknown byte mappings make any CFG *potentially incomplete*.

It never loads a Zend Optimizer binary or executes a PHP source file.
"""
from __future__ import annotations
import argparse
import json
from collections import deque
from pathlib import Path
from zend_serial_parser import parse_binary, decompress_encoded, FormatError

JMP=42
JMPZ=43
JMPNZ=44
JMPZNZ=45
JMPZ_EX=46
JMPNZ_EX=47
RETURN=62
EXIT=79
HANDLE_EXCEPTION=149
BRANCHES={JMP,JMPZ,JMPNZ,JMPZNZ,JMPZ_EX,JMPNZ_EX}
TERMINALS={RETURN,EXIT,HANDLE_EXCEPTION}
# Native PHP 5.2 handlers show non-fallthrough control flow for these
# instructions, but the Encoder operand/target semantics are unverified.
# Never silently interpret them as straight-line instructions.
UNMODELED_CONTROL_FLOW={50,51,77,78,107,108}


def code_string(raw_hex: str, encoding: str = 'cp1251') -> str:
    val=bytes.fromhex(raw_hex)
    text=val.decode(encoding, errors='backslashreplace')
    return repr(text)


def pretty_operand(node: dict, variables: dict[int,str]):
    kind=node['type']
    if kind==1:
        c=node['constant']
        if c['kind']=='string':return code_string(c['raw_hex'])
        if c['kind']=='integer':return str(c['value'])
        if c['kind']=='null':return 'NULL'
        return f"unknown_const({c})"
    if kind==16:return '$'+variables.get(node['word0'],f'CV[{node["word0"]}]')
    if kind==8:return f"UNUSED({node['word0']},{node['word1']})"
    if kind==2:return f"TMP({node['word0']},{node['word1']})"
    if kind==4:return f"VAR({node['word0']},{node['word1']})"
    return f"UNRECOGNIZED_NODE[{kind}]"


def read_jump_target(node: dict, index: int, op: int):
    if node['type']!=8 or node['word1']!=1:
        raise FormatError(f'Non-absolute or unsupported jump operand at #{index} opcode={op}: {node}')
    return node['word0']


def branch_destinations(op: dict, count: int) -> list[tuple[int,str]]:
    """Meaning for JMPZNZ edges deliberately neutral until polarity is verified."""
    num=op['decoded_opcode'];idx=op['index']
    if num==JMP:
        dest=[(read_jump_target(op['op1'],idx,num),'always')]
    elif num in (JMPZ,JMPZ_EX):
        dest=[(read_jump_target(op['op2'],idx,num),'zero'),(idx+1,'nonzero')]
    elif num in (JMPNZ,JMPNZ_EX):
        dest=[(read_jump_target(op['op2'],idx,num),'nonzero'),(idx+1,'zero')]
    elif num==JMPZNZ:
        dest=[(read_jump_target(op['op2'],idx,num),'operand2'),(op['extended_value'],'extended')]
    elif num in TERMINALS:
        dest=[]
    else:
        dest=[(idx+1,'fallthrough')]
    for target,label in dest:
        if not (0<=target<=count):
            raise FormatError(f'Out-of-range jump target {target} at instruction #{idx} ({label}); count={count}')
    return dest


def cfg_for_group(name: str, group: dict) -> dict:
    ops=group['opcodes'];n=len(ops)
    if not ops:return {'name':name,'instruction_count':0,'basic_blocks':[],'edges':[],
                       'unknown_opcode_indices':[],'back_edges':[],'natural_loops':[]}
    assert all(op['index']==i for i,op in enumerate(ops))
    unsafe=[(op['index'],op['decoded_opcode']) for op in ops
            if op['decoded_opcode'] in UNMODELED_CONTROL_FLOW]
    if unsafe:
        raise FormatError(f'Unmodeled control-flow opcodes in {name}: {unsafe[:16]}')
    leaders={0};jump_count=0
    unknown=[x['index'] for x in ops if x['decoded_opcode'] is None]
    for op in ops:
        num=op['decoded_opcode'];i=op['index']
        if num in BRANCHES:
            jump_count+=1
            for d,_ in branch_destinations(op,n):
                if d<n:leaders.add(d)
            if i+1<n:leaders.add(i+1)
        elif num in TERMINALS and i+1<n:
            leaders.add(i+1)
    starts=sorted(leaders)
    blocks=[];instr_to_block={}
    for i,start in enumerate(starts):
        end=(starts[i+1]-1) if i+1<len(starts) else n-1
        block={'id':f'B{start:03d}', 'first':start,'last':end,
               'instruction_indices':list(range(start,end+1)), 'successors':[],
               'predecessors':[]}
        for pc in range(start,end+1):instr_to_block[pc]=block['id']
        blocks.append(block)
    exit_id='EXIT'
    edges=[]
    for block in blocks:
        op=ops[block['last']]
        for target,kind in branch_destinations(op,n):
            to=instr_to_block.get(target,exit_id)
            block['successors'].append({'block':to,'kind':kind,'target_instruction':target})
            edges.append({'from':block['id'],'to':to,'kind':kind,'target_instruction':target})
    idx={b['id']:b for b in blocks}
    for edge in edges:
        if edge['to']!=exit_id:idx[edge['to']]['predecessors'].append(edge['from'])
    # Conservative graph reachability from entry B000
    reachable=set();todo=deque(['B000'])
    while todo:
        b=todo.popleft()
        if b in reachable:continue
        reachable.add(b)
        todo.extend(e['block'] for e in idx[b]['successors'] if e['block']!=exit_id and e['block'] not in reachable)
    for b in blocks:b['reachable']=b['id'] in reachable
    # Dominators on reachable nodes; unknown opcodes can conceal transfers.
    dom={b:set(reachable) for b in reachable};dom['B000']={'B000'}
    changed=True
    while changed:
        changed=False
        for b in blocks:
            ident=b['id']
            if ident not in reachable or ident=='B000':continue
            pred=[p for p in b['predecessors'] if p in reachable]
            shared=set.intersection(*(dom[p] for p in pred)) if pred else set()
            new={ident}|shared
            if new!=dom[ident]:dom[ident]=new;changed=True
    back_edges=[];loops=[]
    for edge in edges:
        src,dst=edge['from'],edge['to']
        if dst in reachable and src in reachable and dst in dom[src]:
            back_edges.append({'from':src,'to':dst,'kind':edge['kind']})
            loop_nodes={src,dst};stack=[src]
            while stack:
                b=stack.pop()
                for p in idx[b]['predecessors']:
                    if p not in reachable or p in loop_nodes:continue
                    loop_nodes.add(p);stack.append(p)
            loops.append({'header':dst,'latch':src,'member_blocks':sorted(loop_nodes,
                                                  key=lambda x:int(x[1:]))})
    return {'name':name,'instruction_count':n,'basic_blocks':blocks,'edges':edges,
            'unknown_opcode_indices':unknown,'branch_instruction_count':jump_count,
            'reachable_blocks':len(reachable),'back_edges':back_edges,
            'natural_loops':loops,'entry':'B000','exit':exit_id,
            'control_flow_complete_for_known_opcodes':not unknown}


def groups_for_parsed(parsed: dict):
    out=[('<main>',parsed['main'])]
    for f in parsed['functions']:
        raw=bytes.fromhex(f['name_hex'])
        out.append((raw.decode('cp1251',errors='replace'),f))
    return out


def as_dot(name: str, cfg: dict, group: dict, names: dict[str,str]):
    lines=['digraph ZendCFG {','  graph [rankdir=TB, fontname="monospace"];',
           '  node [shape=box, fontname="monospace", fontsize=10];',
           '  edge [fontname="monospace", fontsize=9];']
    lines.append('  EXIT [shape=doublecircle, label="EXIT"];')
    for block in cfg['basic_blocks']:
        data=[f"{block['id']} (#{block['first']}..#{block['last']})"]
        for ix in block['instruction_indices'][:5]:
            op=group['opcodes'][ix]
            num=op['decoded_opcode']
            mnemonic=names.get(str(num),str(num)) if num is not None else 'UNKNOWN'
            data.append(f'#{ix:03d} {mnemonic}')
        if len(block['instruction_indices'])>5:data.append('...')
        label='\\l'.join(data)+'\\l'
        style='style="dashed"' if not block['reachable'] else ''
        lines.append(f'  {block["id"]} [label="{label}" {style}];')
    for edge in cfg['edges']:
        label=edge['kind'].replace('"','')
        lines.append(f'  {edge["from"]} -> {edge["to"]} [label="{label}"];')
    lines+=['}', '']
    return '\n'.join(lines)


def as_ir(name: str, cfg: dict, group: dict, names: dict[str,str]):
    vars_={v['index']:bytes.fromhex(v['name_hex']).decode('cp1251',errors='replace')
           for v in group['compiled_vars']}
    lines=[f'# {name} | {cfg["instruction_count"]} serialized instructions | CONTROL-FLOW IR ONLY',
           '# This is not executable PHP. The TMP/VAR location model is not yet reconstructed.',
           '# Jump polarity for JMPZNZ is not established; both labels are preserved.','']
    bystart={b['first']:b for b in cfg['basic_blocks']}
    for op in group['opcodes']:
        i=op['index']
        if i in bystart:lines.append(f'{bystart[i]["id"]}:')
        num=op['decoded_opcode'];name_=names.get(str(num),f'OP_{num}') if num is not None else f'UNKNOWN_0x{op["encoded_opcode"]:02X}'
        chunks=[f'    #{i:03d} line {op["line"]:03d}  {name_}']
        chunks.extend(f'{key}={pretty_operand(op[key],vars_)}' for key in ('result','op1','op2'))
        if num in BRANCHES:
            targets='; '.join(f'{kind} → {"EXIT" if target==len(group["opcodes"]) else "B"+str(target).zfill(3)}'
                 for target,kind in branch_destinations(op,len(group['opcodes'])))
            chunks.append(f'[{targets}]')
        elif num in TERMINALS:chunks.append('[terminates]')
        chunks.append(f'[ext={op["extended_value"]}]')
        lines.append(' '.join(chunks))
    lines.append('')
    return '\n'.join(lines)


def md_summary(configs: list[tuple[str,dict,dict]]) -> str:
    out=['# Zend Encoder — автономное восстановление графа управления', '',
         'Входные опкоды определяются **наблюдательной** таблицей opcode; '
         'при неизвестных байтах граф может быть неполным. PHP не исполнялся.', '',
         '| Блок | Инструкции | Базовые блоки | Переходы | Рёбра CFG | Обратные рёбра | Неизвестные опкоды |',
         '|---|---:|---:|---:|---:|---:|---:|']
    for name,g,c in configs:
        out.append(f'| `{name}` | {c["instruction_count"]} | {len(c["basic_blocks"])} | '
                   f'{c["branch_instruction_count"]} | {len(c["edges"])} | {len(c["back_edges"])} | '
                   f'{len(c["unknown_opcode_indices"])} |')
    out+=['','## Обнаруженные обратные рёбра','']
    for name,g,c in configs:
        out.append(f'### `{name}`')
        if c['back_edges']:
            out.extend(f'- `{e["from"]}` → `{e["to"]}`' for e in c['back_edges'])
        else:out.append('Не обнаружены')
        if c['unknown_opcode_indices']:
            out.append(f'**Внимание:** {len(c["unknown_opcode_indices"])} неизвестных инструкций '
                       'могут содержать переходы — граф не считается исчерпывающим.')
    out += ['', '## Что этот результат НЕ доказывает', '',
            '- Порядок и операнды опкодов прочитаны из сериализованных данных, но '
            'алгоритм для **всех** возможных закодированных байтов ещё не восстановлен.',
            '- Содержимое `TMP` и `VAR` требует анализа временных слотов, прежде чем генерировать выражения PHP.',
            '- Блоки и обратные рёбра ещё не являются восстановленными синтаксическими `if` и `while`.',
            '- Корректность управления в остальных закодированных файлах не подтверждена.', '']
    return '\n'.join(out)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('input',type=Path,help='Encoded .php or decompressed .zend.bin')
    cli.add_argument('--dictionary',type=Path)
    cli.add_argument('--opcode-map',required=True,type=Path)
    cli.add_argument('--out-dir',required=True,type=Path)
    cli.add_argument('--strict-opcodes',action='store_true',help='Refuse incomplete opcode mappings')
    a=cli.parse_args()
    lookup=json.loads(a.opcode_map.read_text());mp=lookup['opcodes'];names=lookup.get('names',{})
    if a.input.suffix=='.bin':streams=[(0,a.input.read_bytes())]
    else:
        if not a.dictionary:cli.error('--dictionary is required for an encoded .php file')
        streams=decompress_encoded(a.input,a.dictionary.read_bytes())
        if not streams:raise SystemExit('No zlib streams with this dictionary')
    a.out_dir.mkdir(parents=True,exist_ok=True)
    report=[]
    for stream_id,(offset,raw) in enumerate(streams,1):
        parsed=parse_binary(raw,mp)
        pairs=[]
        for g_id,(name,group) in enumerate(groups_for_parsed(parsed)):
            cfg=cfg_for_group(name,group)
            if a.strict_opcodes and cfg['unknown_opcode_indices']:
                raise FormatError(f'{name}: {len(cfg["unknown_opcode_indices"])} unknown opcode mappings')
            stem=f'stream{stream_id:02d}_{"main" if g_id==0 else "function"+str(g_id).zfill(2)}'
            (a.out_dir/(stem+'.cfg.json')).write_text(json.dumps(cfg,indent=2,ensure_ascii=False)+'\n')
            (a.out_dir/(stem+'.cfg.dot')).write_text(as_dot(name,cfg,group,names))
            (a.out_dir/(stem+'.ir.txt')).write_text(as_ir(name,cfg,group,names))
            pairs.append((name,group,cfg))
            print(f'{name}: {cfg["instruction_count"]} ops, {len(cfg["basic_blocks"])} blocks, '
                  f'{len(cfg["edges"])} edges, {len(cfg["unknown_opcode_indices"])} unknown opcodes')
        report.append(md_summary(pairs))
    (a.out_dir/'CFG_REPORT.md').write_text('\n\n'.join(report))
    print(f'Done: {a.out_dir}')

if __name__=='__main__':main()
