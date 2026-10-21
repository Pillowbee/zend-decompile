#!/usr/bin/env python3
"""Read-only audit of ALREADY SAVED PHP 5.2 native handler traces.

Does not run PHP, Zend Optimizer, or any supplied PHP program. Archived probe
logs predate this audit. Alignment/handler matches are empirical evidence only:
they do not establish equivalent semantics or a universal Encoder opcode map.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

from zend_calibrate import read_trace, choose_opcode
from zend_assets import OPCODE_MAP, DICTIONARY, BASE
from zend_serial_parser import decompress_encoded, parse_binary

# Two explicitly observed native-stream insertions after FE_FETCH; this is a
# trace alignment annotation, NOT an interpretation of the unknown encoded op.
KNOWN_INSERTIONS = {('fun_all.php', 'out_price'): 65,
                    ('fun_all.php', 'uc_rus'): 17}

TRACE_LOCATIONS = {
    'course_get.php': 'zend_decompiler_v9/reference_traces/course_get.log',
    'user.php': 'zend_decompiler_v9/reference_traces/user.log',
    'fun_all.php': 'zend_decompiler_v9/reference_traces/fun_all.log',
    'gr_wares1.php': 'zend_new_samples/reference_traces/gr_wares1.php.log',
    'links_fun(1).php': 'zend_new_samples/reference_traces/links_fun(1).php.log',
    'import(1).php': 'zend_new_samples/reference_traces/import(1).php.log',
}


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def audit_alignment(project: Path, data_root: Path) -> dict:
    mapping_path = project / OPCODE_MAP.relative_to(BASE)
    dictionary_path = project / DICTIONARY.name
    mapping = json.loads(mapping_path.read_text(encoding='utf-8'))
    evidence = json.loads((mapping_path.parent/'opcode_evidence.json').read_text(encoding='utf-8'))
    dictionary = dictionary_path.read_bytes()
    counts = Counter()
    rows_by_key: dict[str,list[dict]] = defaultdict(list)
    group_reports=[]
    for name, relative_log in TRACE_LOCATIONS.items():
        src=project/'sample_inputs'/name
        log=data_root/relative_log
        streams=decompress_encoded(src,dictionary)
        if len(streams)!=1:
            raise ValueError(f'{name}: expected exactly one encoded stream')
        parsed=parse_binary(streams[0][1])
        groups=[('<main>',parsed['main'])]+[(bytes.fromhex(f['name_hex']).decode('cp1251','replace'),f) for f in parsed['functions']]
        traces=read_trace(log)
        if len(groups)!=len(traces):raise ValueError(f'{name}: group count mismatch')
        for (func,group),native in zip(groups,traces):
            if func!=native['name']:
                raise ValueError(f'{name}: function mismatch: {func} != {native["name"]}')
            ops=group['opcodes']; trace_ops=native['opcodes']
            insertion=KNOWN_INSERTIONS.get((name,func))
            expected=len(ops)+1+(insertion is not None)
            if len(trace_ops)!=expected:
                raise ValueError(f'{name}/{func}: incompatible lengths: {len(ops)} vs {len(trace_ops)}')
            # Fail closed on an unsupported insertion location.
            if insertion is not None:
                if insertion<2 or insertion>=len(ops):raise ValueError('Invalid insertion index')
                if [trace_ops[insertion-2]['ids'],trace_ops[insertion-1]['ids']]!=[[77],[78]]:
                    raise ValueError(f'{name}/{func}: FE_RESET/FE_FETCH anchors absent')
            local=Counter()
            for index, op in enumerate(ops):
                trace_index=index + (insertion is not None and index>=insertion)
                n=trace_ops[trace_index]
                key=f'{index%8}:{op["encoded_opcode"]}'
                mapped=choose_opcode(op,mapping)
                recorded=evidence.get('entries',{}).get(key,{}).get('status','unknown')
                # Ensure source line alignment; a same-length trace with
                # incorrect line numbers is NOT evidence of opcode identity.
                if n['line'] != op['line']:
                    raise ValueError(f'{name}/{func} #{index}: line disagreement')
                ids=n['ids']
                if mapped is None:status='unmapped'
                elif len(ids)!=1:status='handler_undetermined'
                elif mapped!=ids[0]:status='mapped_mismatch'
                elif mapped==140:status='opcode_140_semantics_unresolved'
                elif insertion is not None and index>=insertion:status='matched_post_insertion_alignment'
                else:status='matched_archived_handler_trace'
                row={'file':name,'function':func,'index':index,'key':key,
                     'mapped':mapped,'trace_candidates':ids,'status':status,
                     'line':op['line'],'insertion_adjusted':insertion is not None and index>=insertion,
                     'existing_confidence':recorded}
                rows_by_key[key].append(row)
                local[status]+=1;counts[status]+=1
            group_reports.append({'file':name,'function':func,'serialized_instructions':len(ops),
                'native_instructions':len(trace_ops),'insertion_before_index':insertion,
                'status_counts':dict(sorted(local.items()))})
    keys={}
    for key, rows in sorted(rows_by_key.items()):
        native=sorted({n for r in rows for n in r['trace_candidates']})
        mapping_value=mapping['opcodes'].get(key)
        # 65/66 may share encoded key, depending on operand type. Requiring a
        # single numeric observation makes this conservative for those cases.
        conflicted=len(native)>1 or any(r['status'] in ('mapped_mismatch','unmapped','opcode_140_semantics_unresolved','handler_undetermined') for r in rows)
        keys[key]={'observations':len(rows),'native_candidate_ids':native,
            'mapped_opcode':mapping_value,
            'archived_trace_consistent':not conflicted and bool(rows),
            'has_post_insertion_alignment':any(r['insertion_adjusted'] for r in rows),
            'statuses':dict(sorted(Counter(r['status'] for r in rows).items())),
            'not_independent_proof':True}
    critical={}
    for key in ('1:199',):
        critical[key]={'observations':len(rows_by_key.get(key,[])),
            'records':[r for r in rows_by_key.get(key,[])],
            'resolution':'unknown; no native opcode inferred from neighboring records'}
    occurrences_140=[r for rs in rows_by_key.values() for r in rs if r['mapped']==140]
    critical['opcode_140']={'observations':len(occurrences_140),'records':occurrences_140[:15],
        'resolution':'handler-id collision/context unresolved; preserve current mapping as inferred'}
    return {
        'kind':'archived_native_trace_vs_encoder_alignment_NOT_INDEPENDENT_ORACLE',
        'safety':'No PHP files or Zend binaries were executed during this audit',
        'mapping_sha256':_sha(mapping_path),'dictionary_sha256':_sha(dictionary_path),
        'trace_inputs':[{'source':name,'source_sha256':_sha(project/'sample_inputs'/name),
                         'trace_relative_path':relative,'trace_sha256':_sha(data_root/relative)}
                        for name,relative in TRACE_LOCATIONS.items()],
        'group_count':len(group_reports),'serialized_instructions':sum(x['serialized_instructions'] for x in group_reports),
        'alignment_status_counts':dict(sorted(counts.items())),
        'key_count_observed':len(keys),'key_audit':keys,'groups':group_reports,'critical_unresolved':critical,
        'limitations':['Logs were produced previously; this analysis does not prove their binary provenance.',
                       'Handler matches are not proof of operation or operand semantics.',
                       'Two foreach insertions are aligned by explicit, sample-specific anchors.',
                       'No original-to-encoded paired fixture exists: native-to-serialized round-trip not run.']}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project',type=Path,default=Path(__file__).resolve().parent)
    ap.add_argument('--data-root',type=Path,default=Path('/mnt/data'))
    ap.add_argument('-o','--output',type=Path,required=True)
    ns=ap.parse_args()
    result=audit_alignment(ns.project,ns.data_root)
    ns.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('group_count','serialized_instructions','alignment_status_counts','key_count_observed')},indent=2))


if __name__=='__main__':main()
