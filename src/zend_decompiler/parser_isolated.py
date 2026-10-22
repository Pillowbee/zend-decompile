"""Bounded, subprocess-isolated inspection of UNTRUSTED *decoded* serializer data.

The worker never imports PHP, executes PHP, or evaluates constants. Linux-specific
RLIMIT_AS/RLIMIT_CPU guard untrusted parser inputs. This is an optional inspection
boundary, not a claim that the full restorer is sandboxed.
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from .serial_parser import MAX_BINARY


def parse_isolated(raw:bytes, *, timeout_s:float=5.0, max_memory_mb:int=512) -> dict:
    if len(raw)>MAX_BINARY:
        return {'status':'unsupported','reason':'MAX_BINARY limit exceeded'}
    if not sys.platform.startswith('linux'):
        return {'status':'unsupported','reason':'OS memory/CPU limits implemented only for Linux'}
    if timeout_s<=0 or max_memory_mb<64:
        raise ValueError('Invalid isolated parser limits')
    with tempfile.TemporaryDirectory(prefix='zend_parse_isolated_') as tmp:
        path=Path(tmp)/'stream.bin';path.write_bytes(raw)
        try:
            proc=subprocess.run([sys.executable, '-m', 'zend_decompiler.parser_isolated', '--worker',str(path),str(max_memory_mb)],
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout_s,check=False)
        except subprocess.TimeoutExpired:
            return {'status':'unsupported','reason':'Isolated parser exceeded wall-clock limit'}
        if proc.returncode:
            return {'status':'unsupported','reason':f'Isolated parser stopped (exit {proc.returncode}; possible OS resource limit)'}
        try:
            out=json.loads(proc.stdout)
            if out.get('status') not in ('parsed','unsupported'):
                raise ValueError('Unexpected worker status')
            return out
        except (json.JSONDecodeError,ValueError):
            return {'status':'unsupported','reason':'Invalid worker result'}


def _worker(path:Path,mem_mb:int) -> int:
    import resource
    # RLIMIT_CPU is a second independent limit on total CPU time.
    resource.setrlimit(resource.RLIMIT_CPU,(3,4))
    mem_bytes=mem_mb*1024*1024
    resource.setrlimit(resource.RLIMIT_AS,(mem_bytes,mem_bytes))
    from .serial_parser import parse_binary
    try:
        obj=parse_binary(path.read_bytes())
        result={'status':'parsed','format':obj['format'],
                'group_count':1+len(obj['functions'])+len(obj['experimental_method_groups']),
                'serialized_instructions':len(obj['main']['opcodes'])+sum(len(f['opcodes']) for f in obj['functions'])
                                          +sum(len(f['opcodes']) for f in obj['experimental_method_groups'])}
    except (ValueError,IndexError,KeyError,UnicodeError,OverflowError,RecursionError,MemoryError) as exc:
        result={'status':'unsupported','reason':type(exc).__name__+': '+str(exc)[:300]}
    except Exception as exc:
        result={'status':'unsupported','reason':'Unexpected '+type(exc).__name__+': '+str(exc)[:300]}
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=='__main__':
    if len(sys.argv)==4 and sys.argv[1]=='--worker':
        raise SystemExit(_worker(Path(sys.argv[2]),int(sys.argv[3])))
    raise SystemExit('Use parse_isolated(raw) via Python; worker mode is internal')
