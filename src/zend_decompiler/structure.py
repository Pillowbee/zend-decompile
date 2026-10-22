#!/usr/bin/env python3
"""Experimental structured PHP reconstruction from Zend Encoder CFG.

Only proven straight-line previews and side-effect-free short-circuit joins are
lifted. Structural output is rejected on irreducible CFG, unsupported opcodes,
non-reducible loops, duplicate block emissions, and incomplete coverage.
This is NOT a semantic equivalence proof or a replacement recommendation.
"""
from __future__ import annotations
import argparse
import copy
import json
import hashlib
import networkx as nx
from pathlib import Path
from .assets import OPCODE_MAP, DICTIONARY
from .block_previews import run as previews

class StructureError(ValueError): pass

def insist(pred, why):
    if not pred: raise StructureError(why)

def build_graph(data):
    """Contract strongly verified short-circuit scaffolding into its first block."""
    original={b['id']:copy.deepcopy(b) for b in data['blocks']}
    bypc={b['first']:b['id'] for b in data['blocks']}
    removed={}; folded=[]
    for proof in data['proven_short_circuit_joins']:
        indices=sorted(proof['source_indices'])
        start=min(indices)
        lead=next((b for b in original.values() if b['first'] <= start <= b['last']),None)
        join=original[bypc[proof['join_index']]]
        insist(lead is not None and lead['first'] != join['first'], 'Missing lead for compound condition')
        insist(lead['branch']['opcode'] in ('JMPNZ_EX','JMPZ_EX'), 'No short-circuit at lead')
        insist(join['branch']['opcode'] in ('JMPZ','JMPNZ'), 'Bad join opcode')
        insist(join['branch']['condition']==proof['expression'], 'Proof and join disagree')
        insist(lead['last']==proof['shortcut_indices'][0], 'Unexpected short-circuit lead')
        shortcut_kind='nonzero' if lead['branch']['opcode']=='JMPNZ_EX' else 'zero'
        insist(any(s['kind']==shortcut_kind and s['block']==join['id'] for s in lead['successors']),
               'Short-circuit edge does not reach the proven join')
        # A folded term may contain a call.  The call is inlined into the
        # condition, so it must live in the short-circuit block itself, and no
        # statement of that block may be emitted after the call; otherwise the
        # evaluation order of the call would change.
        for call in proof.get('call_sites',[]):
            call_block=next((b for b in original.values()
                             if b['first']<=call['index']<=b['last']),None)
            insist(call_block is not None and call_block['id']==lead['id'],
                   'Call in a folded term is outside the short-circuit block')
            sources=lead.get('statement_sources') or []
            insist(all(source<call['index'] for source in sources),
                   'Short-circuit block emits statements after a folded call')
        # All intermediary blocks must be pure: no locally emitted statements.
        mids=[b for b in original.values() if lead['last']<b['first'] and b['last']<=join['last']]
        insist(mids and join in mids, 'No blocks to fold')
        for mid in mids:
            insist(not mid['statements'], 'Nonempty block inside short-circuit: '+mid['id'])
            insist(set(range(mid['first'],mid['last']+1)).issubset(indices),
                   'Proof does not account for '+mid['id'])
            insist(mid['id'] not in removed, 'Overlapping proof blocks')
            removed[mid['id']]=lead['id']
        lead['branch']=copy.deepcopy(join['branch'])
        lead['successors']=copy.deepcopy(join['successors'])
        lead['folded_proof_indices']=indices
        folded.append({'lead':lead['id'],'join':join['id'], 'removed':[m['id'] for m in mids],
                       'condition':proof['expression'],'proof_indices':indices})
    kept={name:b for name,b in original.items() if name not in removed}
    insist(len(kept)+len(removed)==len(original),'Node count mismatch')
    graph=nx.DiGraph()
    for bid,b in kept.items():
        graph.add_node(bid)
        for e in b['successors']:
            insist(e['block'] in kept, 'CFG edge into folded block: '+bid+' -> '+e['block'])
            graph.add_edge(bid,e['block'])
    reachable=set(nx.descendants(graph,'B000')) | {'B000'}
    dead=set(graph.nodes)-reachable
    for bid in dead:
        b=kept[bid]
        is_jump_only=(not b['statements'] and b['branch'] is not None and b['branch']['opcode']=='JMP' and b['first']==b['last'])
        is_synthetic_return=(b['statements']==['return NULL;'] and not b['successors'] and b['first']==b['last'])
        insist(is_jump_only or is_synthetic_return, 'Unsafe unreachable block: '+bid)
        graph.remove_node(bid)
        kept.pop(bid)
        removed[bid]='unreachable_jump_only' if is_jump_only else 'synthetic_return'

    exits=[b for b in kept.values() if not b['successors']]
    insist(bool(exits), 'Expected at least one reachable terminal block')
    for end in exits:
        insist(end['statements'] and end['statements'][-1].startswith('return '),
               'Unproven terminal block: '+end['id'])
        graph.add_edge(end['id'],'EXIT')
    return kept,graph,folded,removed


def find_loops(graph, blocks):
    dom=nx.immediate_dominators(graph,'B000')
    dom['B000']='B000'
    # Backedge p -> h if h dominates p.
    def dominates(h,p):
        while True:
            if h==p:return True
            if p==dom[p]:return False
            p=dom[p]
    loops={}
    for p,h in graph.edges:
        if h=='EXIT' or not dominates(h,p): continue
        insist(h in blocks and p in blocks, 'Nonblock loop target')
        nodes={h,p};stack=[p]
        while stack:
            src=stack.pop()
            for pred in graph.predecessors(src):
                if pred not in nodes:
                    nodes.add(pred);stack.append(pred)
        if h in loops:
            loops[h]['nodes'].update(nodes);loops[h]['latches'].add(p)
        else:
            loops[h]={'nodes':nodes,'latches':{p}}
    for h,rec in loops.items():
        block=blocks[h]
        insist(block.get('branch') is not None and block['branch']['opcode'] in ('JMPZ','JMPNZ','JMPZNZ'),
               'Loop header has unknown branch '+h)
        pos={e['kind']:e['block'] for e in block['successors']}
        insist(set(pos) in ({'zero','nonzero'},{'operand2','extended'}), 'Loop branch direction unsupported: '+h)
        inside=[e for e in block['successors'] if e['block'] in rec['nodes']]
        outside=[e for e in block['successors'] if e['block'] not in rec['nodes']]
        insist(len(inside)==len(outside)==1,'Noncanonical loop: '+h)
        insist((inside[0]['kind'], outside[0]['kind']) in (('nonzero','zero'),('extended','operand2')), 'Loop condition polarity unusual: '+h)
        insist(len(rec['latches'])==1,'Multiple latches unsupported: '+h)
        rec['body']=inside[0]['block'];rec['after']=outside[0]['block']
    return loops


class Emitter:
    def __init__(self,blocks,graph,folded,removed):
        self.blocks,self.graph=blocks,graph
        self.folded,self.removed=folded,removed
        self.ipdom=nx.immediate_dominators(graph.reverse(),'EXIT')
        self.loops=find_loops(graph,blocks)
        self.visited=set();self.structure=[];self.lines=[]
    def emit(self,level,line):self.lines.append('    '*level+line)
    def emit_statements(self,b,level,suppress=None):
        lines=b['statements'][:]
        if suppress is not None:
            matches=[s for s in lines if s.strip().rstrip(';')==suppress[1:-1]]
            insist(len(matches)==1 and len(lines)==1,
                  f'Cannot unroll duplicate effect from {b["id"]}: {lines!r} != {suppress!r}')
            lines=[]
        for s in lines:
            # Do not indent physical newlines *inside* PHP string literals.
            # Doing so would silently change emitted HTML byte-for-byte.
            self.emit(level,s)
        return len(lines)
    def region(self,start,stop,level,limit=1000):
        node=start
        for _ in range(limit):
            if node==stop:return
            insist(node in self.blocks, 'Region reaches unexpected '+str(node))
            insist(node not in self.visited, 'Block emitted twice or irreducible CFG: '+node)
            self.visited.add(node)
            b=self.blocks[node]
            branch=b['branch']
            if node in self.loops:
                loop=self.loops[node]
                cond=branch['condition']
                if cond.startswith('(') and cond.endswith(')'):
                    raw=cond[1:-1]
                else:raw=cond
                # If the loop-head assignment is also a pending statement,
                # the condition itself performs that assignment exactly once.
                redundant=cond if b['statements'] else None
                self.emit_statements(b,level,redundant)
                self.emit(level,'while ('+raw+') {')
                self.structure.append({'construct':'while','header':node,'body':loop['body'],'after':loop['after']})
                self.region(loop['body'],node,level+1)
                self.emit(level,'}')
                node=loop['after'];continue
            self.emit_statements(b,level)
            succ=b['successors']
            if len(succ)==0:return
            if len(succ)==1:
                node=succ[0]['block'];continue
            insist(len(succ)==2 and branch is not None,'Unsupported branch at '+node)
            insist(branch['opcode'] in ('JMPZ','JMPNZ'), 'Unsupported branch opcode: '+repr(branch))
            bykind={e['kind']:e['block'] for e in succ}
            insist(set(bykind)=={'zero','nonzero'}, 'Unknown branch polarities')
            join=self.ipdom[node]
            insist(join in self.blocks or join=='EXIT', 'Join not found')
            insist(join!=node, 'Conditional self-join at '+node)
            yes,no=bykind['nonzero'],bykind['zero']
            cond=branch['condition']
            insist(cond,'Missing condition')
            hasyes=(yes!=join);hasno=(no!=join)
            if hasyes and hasno:
                self.emit(level,'if ('+cond+') {')
                self.region(yes,join,level+1)
                self.emit(level,'} else {')
                self.region(no,join,level+1)
                self.emit(level,'}')
            elif hasyes:
                self.emit(level,'if ('+cond+') {')
                self.region(yes,join,level+1)
                self.emit(level,'}')
            elif hasno:
                self.emit(level,'if (!('+cond+')) {')
                self.region(no,join,level+1)
                self.emit(level,'}')
            else:raise StructureError('Redundant decision '+node)
            self.structure.append({'construct':'if','header':node,'true':yes,'false':no,'join':join})
            node=join
        raise StructureError('Recursion limit reached')
    def generate(self,serialized_count):
        self.lines=['<?php','/* EXPERIMENTAL PHP RECONSTRUCTION v13.',' * DO NOT REPLACE PRODUCTION get_wares.php WITHOUT BEHAVIORAL VALIDATION.',
                    ' * Recovered using offline Zend serialization analysis.', ' */']
        self.region('B000','EXIT',0)
        insisted=set(self.blocks)
        insist(self.visited==insisted, 'Incomplete block coverage: '+str(insisted-self.visited))
        original_pcs=set()
        for b in self.blocks.values():original_pcs.update(range(b['first'],b['last']+1))
        proof_pcs=set(x for p in self.folded for x in p['proof_indices'])
        safe_unreachable={int(bid[1:]) for bid,why in self.removed.items() if why in ('unreachable_jump_only','synthetic_return')}
        missing=set(range(serialized_count))-original_pcs-proof_pcs-safe_unreachable
        insist(not missing, 'Unaccounted instructions: '+repr(sorted(missing)))
        # a record of every nonredundant opcode has now been emitted in a block,
        # or folded into a verified short-circuit condition.
        self.lines.append('')
        return '\n'.join(self.lines),{
            'source_instruction_count':serialized_count,
            'original_cfg_blocks':len(self.blocks)+len(self.removed),
            'structured_cfg_blocks':len(self.blocks),
            'emitted_cfg_blocks':len(self.visited),
            'folded_short_circuits':self.folded,
            'structured_constructs':self.structure,
            'loops':list(self.loops),
            'fully_traversed_graph':True,
            'excluded_unreachable_jump_only':sorted(safe_unreachable),
            'syntax_checked':False,
            'semantic_equivalence_proven':False,
            'production_ready':False,
        }


def restore(src:Path, dictionary:Path,mapping:Path):
    data=previews(src,dictionary,mapping)
    insist(data['local_blocks']==len(data['blocks']), 'One or more local blocks unsupported')
    blocks,graph,folded,removed=build_graph(data)
    emitter=Emitter(blocks,graph,folded,removed)
    return emitter.generate(data['total'])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source',type=Path)
    ap.add_argument('--dictionary',type=Path,default=DICTIONARY)
    ap.add_argument('--map',type=Path,default=OPCODE_MAP)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--audit',type=Path,required=True)
    a=ap.parse_args()
    src,audit=restore(a.source,a.dictionary,a.map)
    a.output.write_bytes(src.encode('cp1251'))
    a.audit.write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n')
    print('Emitted',audit['emitted_cfg_blocks'],'of',audit['structured_cfg_blocks'],'semantic blocks')

if __name__=='__main__':main()
