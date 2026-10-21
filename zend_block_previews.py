#!/usr/bin/env python3
"""Offline PHP previews for blocks; inject only individually proven joins.

No PHP script is executed. The output is an analysis artifact, not a program.
"""
import argparse, json
from pathlib import Path
from zend_assets import OPCODE_MAP, DICTIONARY
from zend_crossblock import analyzed_source
from zend_prefix_restore import Decoder,Unsupported


def run(src:Path, dictionary:Path, mapping:Path):
    g,mp,cfg,proofs=analyzed_source(src,dictionary,mapping)
    cvs={v['index']:bytes.fromhex(v['name_hex']) for v in g['compiled_vars']}
    blocks=[]
    for b in cfg['basic_blocks']:
        rec={'id':b['id'],'first':b['first'],'last':b['last'],'successors':b['successors'],
             'instruction_count':b['last']-b['first']+1}
        d=Decoder(g['opcodes'],cvs,mp)
        if b['first'] in proofs:
            proof=proofs[b['first']]
            d.defs[tuple(proof['slot'])]=bytes.fromhex(proof['expression_hex'])
            rec['proven_join']=b['first']
        try:
            result=d.run(b['first'],b['last'])
            rec['status']='local_preview'
            rec['statements']=[s.decode('cp1251','backslashreplace') for s in result.statements]
            rec['branch']=None if result.branch is None else {'opcode':result.branch[0],
                   'condition':result.branch[1].decode('cp1251','backslashreplace'),
                   'target':result.branch[2]}
        except Unsupported as exc:
            rec['status']='unsupported';rec['reason']=str(exc)
        blocks.append(rec)
    return {'source':src.name,'total':len(g['opcodes']),'blocks':blocks,
            'local_blocks':sum(b['status']=='local_preview' for b in blocks),
            'local_instructions':sum(b['instruction_count'] for b in blocks if b['status']=='local_preview'),
            'proven_short_circuit_joins':list(proofs.values()),
            'global_semantic_equivalence':False,'executable_source':False}


def md(data):
    out=['# Zend Decompiler — локальная реконструкция и межблочные условия','',
         '**Исследовательский результат, не исполняемый PHP-файл.**', '',
         f"Обработано локально: **{data['local_blocks']}/{len(data['blocks'])}** блоков, "
         f"**{data['local_instructions']}/{data['total']}** инструкций.", '',
         '## Доказанные короткие логические выражения','']
    for p in data['proven_short_circuit_joins']:
        out.append(f"- При переходе `#{p['join_index']}`: `{p['expression']}` "
                   f"(инструкции `{p['source_indices']}`).")
    out += ['', '## Поблочные фрагменты','']
    for b in data['blocks']:
        out.extend([f"### {b['id']} (#{b['first']}–#{b['last']})",''])
        if b['status']=='unsupported':out += [f"Не восстановлено: `{b['reason']}`",''];continue
        lines=b['statements'][:]
        if b.get('branch'):
            branch=b['branch'];lines.append(f"// BRANCH {branch['opcode']} when ({branch['condition']}) → #{branch['target']}")
        out += ['```php',*[(x if x else '// no emitted statements') for x in lines], '```','']
    out.extend(['## Ограничения','',
                '- Блоки нельзя механически объединять: временные значения могут зависеть от потока управления.',
                '- Поддерживается лишь подмножество опкодов с подтверждённой моделью операндов.',
                '- Не проведено сравнение побочных эффектов и поведения исходной программы.',''])
    return '\n'.join(out)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source',type=Path)
    ap.add_argument('--dictionary',type=Path,default=DICTIONARY)
    ap.add_argument('--map',type=Path,default=OPCODE_MAP)
    ap.add_argument('--json',type=Path,required=True)
    ap.add_argument('--markdown',type=Path,required=True)
    a=ap.parse_args()
    res=run(a.source,a.dictionary,a.map)
    a.json.write_text(json.dumps(res,indent=2,ensure_ascii=False)+'\n')
    a.markdown.write_text(md(res))
    print(f"Translated {res['local_blocks']}/{len(res['blocks'])} blocks "
          f"({res['local_instructions']}/{res['total']} instructions); "
          f"{len(res['proven_short_circuit_joins'])} joins")

if __name__=='__main__':main()
