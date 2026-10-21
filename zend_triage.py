#!/usr/bin/env python3
"""Read-only, literal-free triage for unresolved Zend Encoder recordings.

No Zend Optimizer loading, PHP execution, PHP output, or opcode promotion.
Opcode names in this output are historical *hypotheses*, not confirmations.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from zend_assets import OPCODE_MAP, DICTIONARY

from zend_readonly_dataflow import analyze_file, _validated_evidence
from zend_calibrate import choose_opcode
from zend_serial_parser import decompress_encoded, parse_binary


def _summarize_opcode(op:dict, mapping:dict, evidence:dict) -> dict:
    key=f'{op["index"]%8}:{op["encoded_opcode"]}'
    row=evidence.get(key)
    return {'index':op['index'], 'line':op['line'], 'encoded_key':key,
            'native_opcode_hypothesis':choose_opcode(op,mapping),
            'evidence_status':row.get('status') if row else 'absent',
            'operand_types':{x:op[x]['type'] for x in ('result','op1','op2')}}


def triage_one(source:Path, dictionary:Path, mapping_file:Path,
               mapping:dict, evidence:dict) -> dict:
    diagnostic=analyze_file(source,dictionary,mapping_file)
    streams=decompress_encoded(source,dictionary.read_bytes())
    if len(streams)!=1:
        raise ValueError('Expected exactly one encoded stream')
    parsed=parse_binary(streams[0][1])
    groups=[parsed['main'],*parsed['functions']]
    issues=[];key_counter=Counter();coverage=Counter()
    for report,group in zip(diagnostic['groups'],groups,strict=True):
        coverage[report['status']]+=1
        ops=group['opcodes']
        for item in report.get('uncertain_opcodes',[]):
            idx=item['index'];key=item['key'];key_counter[key]+=1
            neighborhood=[_summarize_opcode(ops[j],mapping,evidence)
                          for j in range(max(0,idx-2),min(len(ops),idx+3))]
            issues.append({'kind':'unknown_or_disputed_mapping','group':report['group'],
                           'index':idx,'key':key,'reason':'mapping not independently confirmed',
                           'hypothesis':item['mapped_opcode'],
                           'evidence_status':item['confidence'],
                           'literal_free_opcode_neighborhood':neighborhood})
        for item in report.get('unmodeled_control_flow',[]):
            issues.append({'kind':'unmodeled_control_flow','group':report['group'],
                           'index':item['index'], 'hypothesis':item['native_opcode']})
        for read in report.get('temporary_uses',[]):
            if read['status'] not in ('multiple_reaching_definitions','possibly_undefined'):
                continue
            issues.append({'kind':'ambiguous_syntactic_definition',
                           'group':report['group'], 'index':read['instruction_index'],
                           'operand':read['operand'], 'slot':read['slot'],
                           'status':read['status'],
                           'reaching_definition_indices':read['reaching_definition_indices'],
                           'structural_paths':read.get('structural_path_witnesses')})
    return {'file':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'groups':len(groups),'coverage':dict(sorted(coverage.items())),
            'unresolved_encoded_key_counts':dict(sorted(key_counter.items())),
            'issues':issues}


def triage(sources:list[Path], dictionary:Path, mapping_file:Path) -> dict:
    evidence=_validated_evidence(mapping_file)
    mapping=json.loads(mapping_file.read_text(encoding='utf-8'))
    return {'kind':'OFFLINE_LITERAL_FREE_OPCODE_AND_CFG_TRIAGE_V27',
            'no_php_executed':True,'no_php_generated':True,
            'semantic_equivalence_proven':False,
            'mapping_sha256':hashlib.sha256(mapping_file.read_bytes()).hexdigest(),
            'dictionary_sha256':hashlib.sha256(dictionary.read_bytes()).hexdigest(),
            'limitations':['Opcode hypotheses inferred from archived alignment, not independently verified.',
                           'Structural CFG paths do not prove executable path feasibility.',
                           'Unmodeled native control flow and disputed mappings are not guessed.'],
            'files':[triage_one(s,dictionary,mapping_file,mapping,evidence) for s in sources]}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources',nargs='+',type=Path)
    parser.add_argument('--dictionary',type=Path,
                        default=DICTIONARY)
    parser.add_argument('--map',type=Path,
                        default=OPCODE_MAP)
    parser.add_argument('-o','--output',type=Path,required=True)
    args=parser.parse_args()
    report=triage(args.sources,args.dictionary,args.map)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([{'file':r['file'],'coverage':r['coverage'],
                       'issues':len(r['issues'])} for r in report['files']],ensure_ascii=False))

if __name__=='__main__':main()
