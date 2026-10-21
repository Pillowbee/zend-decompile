#!/usr/bin/env python3
"""Read-only typed operand and conservative reaching-definition diagnostics.

NO PHP code generation, NO operand rewriting, NO execution. A unique reaching
producer is only a *syntactic candidate*; opcode side effects, aliasing and
native/Encoder operand semantics remain unproven.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from .assets import OPCODE_MAP, DICTIONARY
import json
import hashlib

from .calibrate import choose_opcode
from .cfg import cfg_for_group, UNMODELED_CONTROL_FLOW
from .serial_parser import FormatError
from .serial_parser import decompress_encoded, parse_binary


@dataclass(frozen=True)
class Operand:
    kind: str
    type_id: int
    slot: tuple[int,int] | None = None
    raw_constant: dict | None = None

    @classmethod
    def from_node(cls, node: dict) -> 'Operand':
        tid=node['type']
        if tid==1:return cls('constant',tid,raw_constant=node['constant'])
        if tid==16:return cls('compiled_variable',tid,slot=(node['word0'],node['word1']))
        if tid==8:return cls('unused',tid,slot=(node['word0'],node['word1']))
        if tid in (2,4):return cls('temporary' if tid==2 else 'variable_temp',tid,slot=(node['word0'],node['word1']))
        raise ValueError(f'Unknown operand type {tid}')

    def definition_key(self) -> tuple[int,int,int] | None:
        return (self.type_id,*self.slot) if self.type_id in (2,4) and self.slot else None



def _structural_witnesses(ops: list[dict], cfg: dict, use_index: int,
                          slot: tuple[int,int,int], wanted: list[int],
                          *, state_budget: int = 20000) -> dict:
    """Find reproducible *CFG paths*, not runtime-feasible execution traces.

    State is (instruction PC, last syntactic definition for one operand slot).
    BFS with visited-state dedup terminates on loops. A path's branch decisions
    may be infeasible because conditions and opcode semantics are NOT proven.
    """
    successors={}
    instruction_owner={}
    for b in cfg['basic_blocks']:
        for i in b['instruction_indices']:
            instruction_owner[i]=b['id']
            if i<b['last']:
                successors[i]=[i+1]
            else:
                successors[i]=[e['target_instruction'] for e in b['successors']
                               if e['block']!='EXIT']
    if not ops or len(wanted)>32:
        return {'status':'budget_exceeded','witnesses':[]}
    root=(0,-1)
    parents={root:None}
    queue=deque([root])
    targets=set(wanted)
    found={}
    while queue and len(parents)<state_budget and len(found)<len(targets):
        state=queue.popleft()
        ix,last=state
        if ix==use_index and last in targets and last not in found:
            indices=[]
            trace=state
            while trace is not None:
                indices.append(trace[0]);trace=parents[trace]
            indices.reverse()
            found[last]={'definition_index':last,'instruction_path':indices,
                         'block_path':[instruction_owner[k] for k in indices]}
        new_last=ix if Operand.from_node(ops[ix]['result']).definition_key()==slot else last
        for nxt in successors.get(ix,[]):
            successor=(nxt,new_last)
            if successor not in parents:
                parents[successor]=state
                queue.append(successor)
    return {'status':'complete' if len(found)==len(targets) else
                     ('budget_exceeded' if queue else 'witness_not_found'),
            'witnesses':[found[k] for k in sorted(found)],
            'note':'Structural CFG paths only: condition feasibility and runtime semantics unproven.'}

def read_definitions(group: dict, *, title: str='<main>') -> dict:
    ops=group['opcodes']
    if any(op.get('decoded_opcode') is None for op in ops):
        return {'group':title,'status':'unsupported','reason':'unknown opcode prevents reliable control flow',
                'unknown_indices':[op['index'] for op in ops if op.get('decoded_opcode') is None]}
    unmodeled=[{'index':op['index'], 'native_opcode':op['decoded_opcode']}
               for op in ops if op.get('decoded_opcode') in UNMODELED_CONTROL_FLOW]
    if unmodeled:
        return {'group':title,'status':'unsupported',
                'reason':'unmodeled non-fallthrough/conditional control flow',
                'unmodeled_control_flow':unmodeled}
    try:
        cfg=cfg_for_group(title,group)
    except (FormatError, AssertionError) as exc:
        return {'group':title,'status':'unsupported',
                'reason':'CFG validation failed: '+str(exc)}
    blocks=cfg['basic_blocks']
    by_id={b['id']:b for b in blocks}
    reachable=[b['id'] for b in blocks if b['reachable']]
    if not blocks:
        return {'group':title,'status':'analyzed_syntactically','temporary_uses':[], 'summary':{},'blocks':0}
    preds={b['id']:[x for x in b['predecessors'] if x in reachable] for b in blocks}
    # Explicitly seed undefined at ENTRY for *all* observed TMP/VAR slots.
    # If we instead invent -1 whenever a predecessor state is temporarily
    # empty during fixed-point iteration, that transient -1 circulates around
    # loops forever, yielding false possibly_undefined classifications.
    slots=set()
    for op in ops:
        for position in ('op1','op2','result'):
            key=Operand.from_node(op[position]).definition_key()
            if key is not None:slots.add(key)
    # Per slot, reaching instruction indices, with -1 reserved for the
    # genuine virtual entry-state (never for uninitialized solver state).
    in_defs={b:{} for b in reachable}
    out_defs={b:{} for b in reachable}

    def union_predecessors(bid):
        predecessors=preds[bid]
        universe=set().union(*(set(out_defs[p]) for p in predecessors)) if predecessors else set()
        if bid=='B000':universe.update(slots)
        joined={}
        for slot in universe:
            definitions=set()
            for parent in predecessors:
                definitions.update(out_defs[parent].get(slot,()))
            if bid=='B000':
                # Virtual ENTRY -> B000 remains present even under a backedge.
                definitions.add(-1)
            if definitions:joined[slot]=frozenset(definitions)
        return joined

    def transfer(start, b):
        state=dict(start)
        for i in range(b['first'], b['last']+1):
            op=ops[i]
            r=Operand.from_node(op['result']).definition_key()
            if r is not None:
                state[r]=frozenset({i})
        return state

    # Convergence limit is a diagnostic, never a reason to invent a definition.
    limit=max(10,len(reachable)*(len(ops)+2))
    for iteration in range(limit):
        changed=False
        for bid in reachable:
            next_in=union_predecessors(bid)
            next_out=transfer(next_in,by_id[bid])
            if in_defs[bid]!=next_in or out_defs[bid]!=next_out:
                in_defs[bid]=next_in;out_defs[bid]=next_out;changed=True
        if not changed:break
    else:
        return {'group':title,'status':'unsupported','reason':'reaching-definition fixed-point did not converge',
                'max_iterations':limit}
    owner={i:b['id'] for b in blocks for i in range(b['first'],b['last']+1)}
    reads=[]
    for b in blocks:
        if not b['reachable']:continue
        state=dict(in_defs[b['id']])
        for i in range(b['first'],b['last']+1):
            op=ops[i]
            for position in ('op1','op2'):
                operand=Operand.from_node(op[position])
                key=operand.definition_key()
                if key is None:continue
                defs=sorted(state.get(key,{-1}))
                if defs==[-1]:resolution='no_reaching_definition'
                elif -1 in defs:resolution='possibly_undefined'
                elif len(defs)>1:resolution='multiple_reaching_definitions'
                else:resolution='one_reaching_definition_syntactic_only'
                row={'block':b['id'],'instruction_index':i,'operand':position,
                     'slot':list(key),'reaching_definition_indices':defs,
                     'status':resolution,
                     'cross_block':len(defs)==1 and defs[0]>=0 and owner.get(defs[0])!=b['id']}
                if len(defs)>1:
                    row['structural_path_witnesses']=_structural_witnesses(
                        ops,cfg,i,key,defs)
                reads.append(row)
            result=Operand.from_node(op['result']).definition_key()
            if result is not None:state[result]=frozenset({i})
    count=Counter(r['status'] for r in reads)
    cross=sum(r['cross_block'] for r in reads)
    return {'group':title,'status':'analyzed_syntactically',
            'note':'NO PHP expression substitution. Alias/side effects and opcode semantics are NOT proven.',
            'instructions':len(ops),'blocks':len(blocks),'reachable_blocks':len(reachable),
            'iteration_count':iteration+1,
            'summary':{'temporary_operand_uses':len(reads),'cross_block_unique_syntactic_producers':cross,
                       'by_status':dict(sorted(count.items()))},
            'temporary_uses':reads}


def _validated_evidence(mapping_path: Path) -> dict:
    """Check source-to-evidence hashes; never treat an unauthenticated opcode
    confidence label as proof.  These hashes establish *file consistency*,
    not empirical correctness of the mapping itself.
    """
    metadata_path=mapping_path.with_name(mapping_path.name+'.meta.json')
    if not metadata_path.is_file():
        raise ValueError('Opcode metadata absent: cannot certify read-only CFG mapping')
    metadata=json.loads(metadata_path.read_text(encoding='utf-8'))
    mapping_hash=hashlib.sha256(mapping_path.read_bytes()).hexdigest()
    if metadata.get('mapping_file')!=mapping_path.name or metadata.get('mapping_sha256')!=mapping_hash:
        raise ValueError('Opcode mapping/metadata SHA256 mismatch')
    evidence_path=mapping_path.with_name(metadata['evidence_file'])
    if not evidence_path.is_file():
        raise ValueError('Opcode evidence file absent')
    data=evidence_path.read_bytes()
    if metadata.get('evidence_sha256')!=hashlib.sha256(data).hexdigest():
        raise ValueError('Opcode evidence SHA256 mismatch')
    evidence=json.loads(data.decode('utf-8'))
    if evidence.get('mapping_sha256')!=mapping_hash:
        raise ValueError('Opcode evidence references a different mapping')
    return evidence['entries']


def analyze_file(src:Path, dictionary:Path, mapping_path:Path) -> dict:
    raw=decompress_encoded(src,dictionary.read_bytes())
    if len(raw)!=1:raise ValueError('Expected exactly one encoded stream')
    parsed=parse_binary(raw[0][1]);mapping=json.loads(mapping_path.read_text(encoding='utf-8'))
    evidence=_validated_evidence(mapping_path)
    result=[]
    groups=[('<main>',parsed['main'])]+[(bytes.fromhex(f['name_hex']).decode('cp1251',errors='replace'),f) for f in parsed['functions']]
    for name,group in groups:
        uncertain=[]
        for op in group['opcodes']:
            key=f'{op["index"]%8}:{op["encoded_opcode"]}'
            decoded=choose_opcode(op,mapping)
            observed=evidence.get(key)
            # A byte that merely maps to native 140 is not a verified
            # DECLARE_INHERITED_CLASS.  Archived data show conflicting call
            # contexts.  Never derive a 'complete' CFG from such a guess.
            if (decoded==140 or observed is None or
                    observed.get('status')=='unknown' or decoded is None):
                uncertain.append({'index':op['index'],'key':key,
                                  'mapped_opcode':decoded,
                                  'confidence':observed.get('status') if observed else 'absent'})
                op['decoded_opcode']=None
            else:
                op['decoded_opcode']=decoded
        report=read_definitions(group,title=name)
        if uncertain:report['uncertain_opcodes']=uncertain
        result.append(report)
    return {'file':src.name,'kind':'READ_ONLY_SYNTACTIC_REACHING_DEFINITIONS',
            'semantic_equivalence_proven':False,'php_generated':False,
            'mapping_confidence':'historical empirical mapping; unknown entries quarantined',
            'groups':result}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('--dictionary',type=Path,default=DICTIONARY)
    p.add_argument('--map',type=Path,default=OPCODE_MAP)
    p.add_argument('-o','--output',type=Path,required=True)
    args=p.parse_args()
    data=analyze_file(args.source,args.dictionary,args.map)
    args.output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([{'group':g['group'],'status':g['status'],'summary':g.get('summary')} for g in data['groups']],ensure_ascii=False))

if __name__=='__main__':main()
