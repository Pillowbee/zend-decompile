"""Compile-only PHP 5.2 diagnostic probe reader for OWN TEST SOURCES ONLY.

Does not execute source code. Probe output is a *native* Zend op_array dump,
not an SSG Team/Zend Encoder serialization and cannot be fed to the restorer.
"""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
from pathlib import Path

OP = re.compile(r'^\[probe\] #(\d+) opcode=(\d+) handler=0x[0-9a-f]+ line=(\d+) extended=(\d+)')
FN = re.compile(r'^\[probe\] function_name=(.*)$')
ARRAY = re.compile(r'^\[probe\] op_array=')
CV = re.compile(r'^\[probe\] compiled_var idx=(\d+) len=(\d+) hex=([0-9a-f]*)$')

class ProbeFormatError(ValueError):
    pass


def read_probe_log(content: str) -> dict:
    """Normalize stable data; deliberately discard ASLR-dependent addresses."""
    if 'No syntax errors detected' not in content:
        raise ProbeFormatError('PHP lint did not report successful compilation')
    groups=[]; name=None; current=None
    for line in content.splitlines():
        m=FN.match(line)
        if m:
            name=m.group(1)
            continue
        if ARRAY.match(line):
            if name is None:raise ProbeFormatError('op_array without function name')
            current={'name':name, 'opcodes':[], 'compiled_vars':[]}
            groups.append(current)
            continue
        m=CV.match(line)
        if m:
            if current is None:raise ProbeFormatError('CV without op_array')
            idx,length,hx=int(m.group(1)),int(m.group(2)),m.group(3)
            if len(bytes.fromhex(hx))!=length:raise ProbeFormatError('Incorrect CV length')
            current['compiled_vars'].append({'index':idx,'name_hex':hx})
            continue
        m=OP.match(line)
        if m:
            if current is None:raise ProbeFormatError('Opcode without op_array')
            idx,code,lineno,ext=map(int,m.groups())
            if idx!=len(current['opcodes']):raise ProbeFormatError('Out-of-order instruction number')
            current['opcodes'].append({'index':idx,'opcode':code,'line':lineno,'extended':ext})
    if not groups or not any(x['opcodes'] for x in groups):
        raise ProbeFormatError('No opcode dump detected')
    return {'format':'php52-native-oparray-probe-v1', 'groups':groups,
            'total_instructions':sum(len(x['opcodes']) for x in groups)}


def compile_own_fixture(source:Path, owned_root:Path, php:Path, extension:Path, *, library_dir:Path|None=None) -> dict:
    """Only an allowlisted fixture under corpus/own_sources may be compiled."""
    src=source.resolve(strict=True)
    if not src.is_file() or src.suffix!='.php' or not src.is_relative_to(owned_root.resolve(strict=True)):
        raise ValueError('Compile-only oracle requires an owned PHP fixture')
    if src.is_symlink():raise ValueError('Symlinked fixture refused')
    env={}
    import os
    env=os.environ.copy()
    if library_dir:env['LD_LIBRARY_PATH']=str(library_dir)
    result=subprocess.run([str(php.resolve()),'-n','-d',f'zend_extension={extension.resolve()}', '-l',str(src)],
                          capture_output=True,timeout=15,env=env)
    if result.returncode:
        raise ProbeFormatError('PHP -l/probe failed: '+(result.stderr+result.stdout).decode('utf-8','replace')[:500])
    parsed=read_probe_log((result.stderr+result.stdout).decode('utf-8','replace'))
    parsed['fixture_sha256']=hashlib.sha256(src.read_bytes()).hexdigest()
    parsed['probe_sha256']=hashlib.sha256(extension.read_bytes()).hexdigest()
    parsed['php_sha256']=hashlib.sha256(php.read_bytes()).hexdigest()
    return parsed


def round_trip_unavailable(reason:str='No verified adapter from PHP 5.2 native op_array dump to SSG Team serialized operand format') -> dict:
    return {'status':'not_run','reason':reason}


def corpus_metrics(manifest:dict) -> dict:
    """No phantom 0% success: ineligible fixtures have null restoration rates."""
    programs=manifest['programs']; ng=sum(p['function_count'] for p in programs)
    return {'total_own_files':len(programs),'total_own_functions':ng,
            'compile_only_files':sum(p['compile_only_passed'] for p in programs),
            'compile_only_functions':sum(p['function_count'] for p in programs if p['compile_only_passed']),
            'restoration_eligible_files':0,'restoration_eligible_functions':0,
            'restoration_success_fraction_files':None,'restoration_success_fraction_functions':None,
            'round_trip':round_trip_unavailable()}


def generate_fixture_manifest(source_dir:Path,dump_dir:Path) -> dict:
    programs=[]
    for src in sorted(source_dir.glob('*.php')):
        parsed=read_probe_log((dump_dir/(src.stem+'.log')).read_text(encoding='utf-8'))
        programs.append({'name':src.name,'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
                         'compile_only_passed':True,'function_count':sum(g['name']!='<main>' for g in parsed['groups']),
                         'group_count':len(parsed['groups']), 'native_opcode_count':parsed['total_instructions']})
    return {'kind':'OWN_SOURCE_COMPILE_ONLY_NOT_DECOMPILER_INPUT','programs':programs}
