#!/usr/bin/env python3
"""Build an evidence-based opcode lookup from Zend 5.2 compile-only probe traces.

Research scope: sample-specific observations; does not reconstruct an unknown
Zend Encoder substitution cipher, and never executes the protected PHP files.
Alignment patches for two foreach cases are explicit and fail closed.
"""
from __future__ import annotations
import argparse
import collections
import json
import re
from pathlib import Path
from zend_serial_parser import decompress_encoded, parse_binary

TRACE_OPCODE = re.compile(r'^\[probe\] #(\d+) opcode=(\d+) handler=0x[0-9a-f]+ line=(\d+).* mapmatches=([\d,]*)$')
FUNC_RE = re.compile(r'^\[probe\] function_name=(.*)$')
# Independently identified extra runtime instruction immediately after FE_FETCH,
# in both foreach loops. The 1-byte serialized opcode at S65/S17 still exists;
# only alignment is corrected, not interpreted by guessing its handler.
INSERTION = {('fun_all.php','out_price'):65, ('fun_all.php','uc_rus'):17}
SEND_VARIANTS = {'3:139', '6:236'}


def read_trace(path: Path) -> list[dict]:
    txt = path.read_text(errors='replace')
    if 'No syntax errors detected' not in txt:
        raise ValueError(f'PHP -l did not finish successfully: {path}')
    res = []; fn = None
    for line in txt.splitlines():
        fm = FUNC_RE.match(line)
        if fm:fn=fm[1]
        if line.startswith('[probe] op_array='):
            res.append({'name':fn,'opcodes':[]})
        mo = TRACE_OPCODE.match(line)
        if mo:
            if not res:raise ValueError('Opcode with no function container')
            idx=int(mo[1]); cur=res[-1]['opcodes']
            if idx!=len(cur):raise ValueError(f'Unexpected runtime opcode index {idx}')
            cur.append({'index':idx,'line':int(mo[3]),'ids':[int(x) for x in mo[4].split(',') if x]})
    return res


def source_groups(parsed: dict) -> list[tuple[str, dict]]:
    return [('<main>',parsed['main'])]+[(bytes.fromhex(f['name_hex']).decode('cp1251',errors='replace'),f) for f in parsed['functions']]


def calibrate(inputs: dict[str,Path], traces: dict[str,Path], dictionary: bytes, base: dict) -> tuple[dict,dict]:
    obs=collections.defaultdict(list); comparisons=[]; anomalous=[]
    for filename,src in inputs.items():
        streams=decompress_encoded(src,dictionary)
        if len(streams)!=1:raise ValueError(f'Expected one compressed stream: {filename}')
        parsed=parse_binary(streams[0][1])
        groups=source_groups(parsed)
        runtime=read_trace(traces[filename])
        if len(groups)!=len(runtime):raise ValueError(f'{filename}: function count disagrees')
        for (name,g),rt in zip(groups,runtime):
            if name!=rt['name']:raise ValueError(f'{filename}: function order disagrees: {name} vs {rt["name"]}')
            ops=g['opcodes']; run=rt['opcodes']
            insertion=INSERTION.get((filename,name))
            expected=len(ops)+1+(insertion is not None)
            if len(run)!=expected:
                raise ValueError(f'{filename}:{name}: expected {expected} runtime ops, got {len(run)}')
            if insertion is not None:
                # Validate both anchoring opcodes immediately before insertion.
                if [run[insertion-2]['ids'],run[insertion-1]['ids']] != [[77],[78]]:
                    raise ValueError(f'{filename}:{name}: expected FE_RESET/FE_FETCH before insertion')
                if run[insertion]['line'] != ops[insertion]['line']:
                    raise ValueError(f'{filename}:{name}: unexpected source line at inserted opcode')
                anomalous.append({'file':filename,'function':name,'index':insertion})
            good=0; undecidable=0
            for i,op in enumerate(ops):
                r=run[i + (1 if insertion is not None and i>=insertion else 0)]
                if r['line']!=op['line']:
                    raise ValueError(f'{filename}:{name}: source line mismatch at #{i}, {r["line"]} != {op["line"]}')
                k=f'{i%8}:{op["encoded_opcode"]}'
                ids=r['ids']
                if len(ids)==1:
                    obs[k].append({'opcode':ids[0],'file':filename,'function':name,'index':i,
                                   'op1_type':op['op1']['type']})
                    good+=1
                else:undecidable+=1
            comparisons.append({'file':filename,'function':name,'serialized':len(ops),
                                'runtime':len(run),'unambiguous':good,'unidentified':undecidable})
    new=dict(base['opcodes']); disputes={}
    for key,rows in sorted(obs.items()):
        found=sorted(set(x['opcode'] for x in rows))
        if len(found)==1:
            if key in new and new[key]!=found[0]:
                raise ValueError(f'Existing mapping contradicted for {key}: {new[key]} vs {found[0]}')
            new[key]=found[0]
        else:
            if key not in SEND_VARIANTS or found != [65,66]:
                raise ValueError(f'Unexpected opcode collision for {key}: {found}')
            for row in rows:
                expected=65 if row['op1_type']==1 else 66
                if row['opcode']!=expected:
                    raise ValueError(f'Non-operand-resolvable collision at {key}: {row}')
            # Map entry remains the default, but disassembler overrides by operand type.
            disputes[key]={'observed':found,'reason':'SEND_VAL/SEND_VAR selected by operand type',
                           'observations':len(rows)}
    # Opcode 49 = PHP 5.2 SWITCH_FREE. The validated inserted-foreach sections
    # contain an opcode with result UNUSED/op1 TMP/op2 UNUSED immediately before
    # the extra runtime instruction; specialized handlers are not disambiguated
    # by the handler oracle, so mark this as provisional, not 'verified'.
    names=dict(base['names'])
    names.update({'2':'SUB','9':'BW_OR','10':'BW_AND','13':'BOOL_NOT','15':'IS_IDENTICAL',
                  '16':'IS_NOT_IDENTICAL','20':'IS_SMALLER_OR_EQUAL','21':'CAST','22':'QM_ASSIGN',
                  '23':'ASSIGN_ADD','24':'ASSIGN_SUB','29':'ASSIGN_SR','31':'ASSIGN_BW_OR',
                  '32':'ASSIGN_BW_AND','36':'POST_INC','37':'POST_DEC','40':'ECHO','41':'PRINT',
                  '44':'JMPNZ','46':'JMPZ_EX','47':'JMPNZ_EX','48':'CASE','49':'SWITCH_FREE',
                  '50':'BRK','51':'CONT','52':'BOOL','54':'ADD_CHAR','57':'BEGIN_SILENCE',
                  '58':'END_SILENCE','60':'DO_FCALL','63':'RECV','64':'RECV_INIT','67':'SEND_REF',
                  '70':'FREE','74':'UNSET_VAR','75':'UNSET_DIM','76':'UNSET_OBJ',
                  '77':'FE_RESET','78':'FE_FETCH','79':'EXIT','80':'FETCH_R',
                  '82':'FETCH_OBJ_R','85':'FETCH_OBJ_W','86':'FETCH_RW','87':'FETCH_DIM_RW',
                  '89':'FETCH_IS','90':'FETCH_DIM_IS','91':'FETCH_OBJ_IS',
                  '94':'FETCH_OBJ_FUNC_ARG','96':'FETCH_DIM_UNSET','98':'FETCH_DIM_TMP_VAR',
                  '99':'FETCH_CONSTANT','101':'EXT_STMT','106':'SEND_VAR_NO_REF',
                  '112':'INIT_METHOD_CALL','113':'INIT_STATIC_METHOD_CALL',
                  '114':'ISSET_ISEMPTY_VAR','115':'ISSET_ISEMPTY_DIM_OBJ',
                  '136':'ASSIGN_OBJ','137':'OP_DATA','139':'DECLARE_CLASS',
                  '141':'DECLARE_FUNCTION','147':'ASSIGN_DIM'})
    result={'description':'Empirical Zend 5.2 opcode mapping for five supplied samples; not a universal cipher',
            'names':names,'opcodes':new,
            'conditional_send_keys':sorted(disputes),
            'unresolved_foreach_key':'1:199',
            'provenance':'PHP 5.2.17 -l with Zend Optimizer and an opcode-handler probe; not execution of business logic'}
    return result,{'trace_groups':comparisons,'insertions':anomalous,'conditional_send':disputes,
                   'observations':sum(len(v) for v in obs.values()),'keys_observed':len(obs),
                   'keys_before':len(base['opcodes']),'keys_after':len(new)}


def choose_opcode(op:dict,mapping:dict) -> int|None:
    k=f'{op["index"]%8}:{op["encoded_opcode"]}'
    if k in mapping.get('conditional_send_keys',[]):
        return 65 if op['op1']['type']==1 else 66
    return mapping['opcodes'].get(k)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--samples',type=Path,default=Path('samples'))
    ap.add_argument('--traces',type=Path,default=Path('reference_traces'))
    ap.add_argument('--old-map',type=Path,required=True,help='Explicit historical map for trace calibration; no implicit downgrade')
    ap.add_argument('--dictionary',type=Path,default=Path('samples/zend_verified_dictionary.bin'))
    ap.add_argument('--out',type=Path,default=Path('calibrated_opcode_map.json'))
    ap.add_argument('--audit',type=Path,default=Path('calibration_report.json'))
    args=ap.parse_args()
    names=['course_get.php','user.php','fun_all.php']
    inputs={n:args.samples/n for n in names}
    logs={n:args.traces/(Path(n).stem+'.log') for n in names}
    result,report=calibrate(inputs,logs,args.dictionary.read_bytes(),json.loads(args.old_map.read_text()))
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    args.audit.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('Calibrated opcode keys:',report['keys_before'],'->',report['keys_after'])
    print('Conditional SEND keys:',list(report['conditional_send']))

if __name__=='__main__':main()
