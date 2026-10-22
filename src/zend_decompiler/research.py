#!/usr/bin/env python3
"""Generate verified-per-parser fragments; never emit a partial fun_all.php as complete."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from .assets import OPCODE_MAP, DICTIONARY
from .serial_parser import decompress_encoded,parse_binary
from .calibrate import choose_opcode
from .restore_core import build_group, function_parameters_after_decode
from .encoder_calls import declared_callees
from .state import state_emit
from .engine import __version__


def research(source:Path, dictionary:Path, mapping_file:Path, out:Path):
    streams=decompress_encoded(source,dictionary.read_bytes())
    if len(streams)!=1:raise ValueError('Only single-stream samples supported')
    parsed=parse_binary(streams[0][1]);mapping=json.loads(mapping_file.read_text())
    groups=[('<main>',parsed['main'])]+[(bytes.fromhex(g['name_hex']).decode('ascii'),g) for g in parsed['functions']]
    symbols=parsed.get('header_symbols',[])
    callees=declared_callees(parsed,mapping)
    report={'version':'v'+__version__.split('.')[0],'source':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'total_serialized_instructions':sum(len(x['opcodes']) for _,x in groups),
            'groups':[],'complete_source_generated':False,
            'behavioral_equivalence_proven':False,'production_ready':False}
    out.mkdir(parents=True,exist_ok=True)
    frag=out/(source.stem+'_validated_fragments');frag.mkdir(exist_ok=True)
    total_done=0
    for name,g in groups:
        for op in g['opcodes']:op['decoded_opcode']=choose_opcode(op,mapping)
        unknown=[op['index'] for op in g['opcodes'] if op['decoded_opcode'] is None]
        row={'name':name,'serialized_instructions':len(g['opcodes']),
             'unknown_opcodes':unknown,'generated':False,'strategy':None}
        if unknown:
            row['failure']='Unknown opcodes: '+repr(unknown)
        else:
            try:
                params=[] if name=='<main>' else function_parameters_after_decode(g,mapping)
                try:
                    body,audit=build_group(g,mapping,name,symbols,callees)
                    row['strategy']='structured_php'
                except Exception as structure_exc:
                    try:
                        body,audit=state_emit(g,mapping,name,symbols,callees)
                        row['strategy']='explicit_php52_state_machine'
                        row['structured_failure']=str(structure_exc)
                    except Exception as fallback_exc:
                        raise RuntimeError('Structured: '+str(structure_exc)+'; state: '+str(fallback_exc)) from fallback_exc
                if name!='<main>':
                    output=['<?php','/* EXPERIMENTAL function fragment, not complete fun_all.php. */',
                        'function '+name+'('+', '.join(params)+') {',
                        *['    '+line for line in body],'}','']
                    (frag/(name+'.php')).write_bytes('\n'.join(output).encode('cp1251'))
                else:
                    # Main statements without the remaining functions must not be
                    # shipped as a runnable replacement PHP file.
                    (out/'main_fragment_READ_ONLY.txt').write_bytes('\n'.join(body).encode('cp1251'))
                row['generated']=True
                total_done+=len(g['opcodes'])
            except Exception as exc:row['failure']=str(exc)
        report['groups'].append(row)
    report['complete_groups']=sum(x['generated'] for x in report['groups'])
    report['generated_instructions']=total_done
    report['complete_source_generated']=all(x['generated'] for x in report['groups'])
    (out/(source.stem+'.analysis.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source',type=Path)
    ap.add_argument('--dictionary',type=Path,default=DICTIONARY)
    ap.add_argument('--map',type=Path,default=OPCODE_MAP)
    ap.add_argument('-o','--output-dir',type=Path,required=True)
    a=ap.parse_args()
    r=research(a.source,a.dictionary,a.map,a.output_dir)
    print('research',r['complete_groups'],'/',len(r['groups']),'groups generated;',
          r['generated_instructions'],'/',r['total_serialized_instructions'],'opcode records')
if __name__=='__main__':main()
