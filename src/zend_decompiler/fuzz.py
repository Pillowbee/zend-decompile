"""Deterministic mutation campaign for the SERIALIZATION PARSER, not PHP runtime.

Unexpected exceptions cause exact mutated bytes and metadata to be saved for regression.
This tool does not execute PHP input or generated code. OS-isolated samples can be
checked with --isolate-every N (Linux, bounded memory and wall/CPU time).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from pathlib import Path

from .serial_parser import parse_binary, decompress_encoded, FormatError
from .parser_isolated import parse_isolated

ALLOWED=(ValueError,IndexError,KeyError,UnicodeError,OverflowError,RecursionError,MemoryError)


def run_campaign(raw:bytes, *, seed:int, mutations:int, crash_dir:Path, isolate_every:int=0) -> dict:
    rng=random.Random(seed)
    cases=[('empty',b''),('prefix_1',raw[:1]),('prefix_25',raw[:25]),
           ('half',raw[:len(raw)//2]),('no_final_byte',raw[:-1])]
    for k in range(mutations):
        item=bytearray(raw)
        if not item:break
        i=rng.randrange(len(item)); item[i]^=rng.randrange(1,256)
        cases.append((f'mutation_{k}',bytes(item)))
    stats={'seed':seed,'mutations':mutations,'total_cases':len(cases),
           'parsed':0,'rejected':0,'isolation_failures':0,'unexpected':0,'crashes':[]}
    for n,(label,blob) in enumerate(cases):
        try:
            parse_binary(blob)
            stats['parsed']+=1
        except ALLOWED:
            stats['rejected']+=1
        except BaseException as exc:
            # Persist the actual unexpected test case before failing CI.
            crash_dir.mkdir(parents=True,exist_ok=True)
            digest=hashlib.sha256(blob).hexdigest()
            path=crash_dir/f'{digest[:24]}.bin'
            path.write_bytes(blob)
            (crash_dir/f'{digest[:24]}.json').write_text(json.dumps({
                'seed':seed,'case':label,'size':len(blob),
                'exception':type(exc).__name__, 'message':str(exc)[:250]},indent=2)+'\n')
            stats['unexpected']+=1
            stats['crashes'].append(str(path))
        if isolate_every>0 and n%isolate_every==0:
            r=parse_isolated(blob)
            if r['status'] not in ('parsed','unsupported'):
                stats['isolation_failures']+=1
    return stats


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True,help='Encoded input is READ ONLY and never executed')
    p.add_argument('--dictionary',type=Path,required=True)
    p.add_argument('--seed',type=int,default=20261021)
    p.add_argument('--mutations',type=int,default=150)
    p.add_argument('--isolate-every',type=int,default=20)
    p.add_argument('--crash-dir',type=Path,default=Path('tests/fuzz_regressions'))
    p.add_argument('--report',type=Path)
    a=p.parse_args(argv)
    streams=decompress_encoded(a.source,a.dictionary.read_bytes())
    if len(streams)!=1:raise ValueError('Exactly one stream expected for fuzz campaign')
    report=run_campaign(streams[0][1],seed=a.seed,mutations=a.mutations,
                        crash_dir=a.crash_dir,isolate_every=a.isolate_every)
    if a.report:
        a.report.parent.mkdir(parents=True,exist_ok=True)
        a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 1 if report['unexpected'] or report['isolation_failures'] else 0

if __name__=='__main__':raise SystemExit(main())
