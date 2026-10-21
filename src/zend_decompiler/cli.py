#!/usr/bin/env python3
"""Offline Zend PHP 5.2 recovery research tool. No PHP source is executed."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .engine import restore_result, __version__
from .assets import GOLDEN, OPCODE_MAP, DICTIONARY, DATA_DIR
from .batch import batch,atomic_bytes,write_candidate,syntax_check,json_bytes

from .assets import BASE


def main(argv=None):
    p=argparse.ArgumentParser(prog='zend-decompiler',description=__doc__)
    p.add_argument('--version',action='version',version=__version__)
    sub=p.add_subparsers(dest='command',required=True)
    for cmd in ('restore','batch','audit','validate'):
        s=sub.add_parser(cmd)
        if cmd=='validate':
            s.add_argument('--php-linter',type=Path)
            s.add_argument('--lib-dir',type=Path)
        else:
            s.add_argument('source',type=Path)
            s.add_argument('--dictionary',type=Path,default=DICTIONARY)
            s.add_argument('--map',type=Path,default=OPCODE_MAP)
            s.add_argument('--isolate-parser',action='store_true',help='Linux-only bounded parser preflight for untrusted input')
            if cmd!='audit':s.add_argument('-o','--output',type=Path,required=True)
            if cmd=='restore':
                s.add_argument('--audit',type=Path,required=True)
                s.add_argument('--php-linter',type=Path)
                s.add_argument('--lib-dir',type=Path)
            if cmd=='batch':
                s.add_argument('--recursive',action='store_true')
                s.add_argument('--php-linter',type=Path)
                s.add_argument('--lib-dir',type=Path)
    # Read-only diagnostics; existing restore/batch APIs unchanged.
    diag=sub.add_parser('dataflow',help='inspect syntactic TMP/VAR reaching definitions; no PHP output')
    diag.add_argument('source',type=Path)
    diag.add_argument('--dictionary',type=Path,default=DICTIONARY)
    diag.add_argument('--map',type=Path,default=OPCODE_MAP)
    diag.add_argument('-o','--output',type=Path,required=True)
    align=sub.add_parser('align-archived',help='audit saved handler traces; never runs PHP')
    align.add_argument('--data-root',type=Path,required=True,help='root containing historical probe logs')
    align.add_argument('-o','--output',type=Path,required=True)
    a=p.parse_args(argv)
    if a.command=='dataflow':
        from .readonly_dataflow import analyze_file
        result=analyze_file(a.source,a.dictionary,a.map)
        atomic_bytes(a.output,json_bytes(result))
        print(f'Read-only CFG dataflow: {len(result["groups"])} groups; PHP output not generated')
        return 0
    if a.command=='align-archived':
        from .alignment_audit import audit_alignment
        result=audit_alignment(BASE,a.data_root)
        atomic_bytes(a.output,json_bytes(result))
        print(f'Archived-trace audit: {result["serialized_instructions"]} instructions; no mappings changed')
        return 0
    if a.command=='validate':
        import unittest
        # Wheels do not ship golden fixtures. Never call an empty test suite success.
        if not (BASE/'tests/test_golden.py').exists() or not (GOLDEN/'manifest.json').exists():
            print('Full golden validation requires the source distribution with tests/ and golden/reference/',file=sys.stderr)
            return 2
        suite=unittest.defaultTestLoader.discover(str(BASE/'tests'))
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    if a.command=='batch':
        r=batch(a.source,a.output,a.dictionary,a.map,a.recursive,a.php_linter,a.lib_dir,a.isolate_parser)
        print(json.dumps({k:r[k] for k in ('total','generated','unsupported','not_encoded')},ensure_ascii=False))
        return 0 if r['unsupported']==0 else 2
    result=restore_result(a.source,a.dictionary,a.map,isolate_parser=a.isolate_parser)
    if a.command=='audit':
        print(json.dumps(result.audit,ensure_ascii=False,indent=2))
        return 0 if result.status=='candidate_generated' else 2
    if result.status!='candidate_generated':
        # An audit is written even if restoration fails; never write a partial .php.
        atomic_bytes(a.audit,json_bytes(result.audit))
        print(f'{result.status}: {result.reason}',file=sys.stderr)
        return 2
    if a.php_linter:
        passed,msg=syntax_check(result.code,a.php_linter,library_dir=a.lib_dir)
        result.audit['syntax_checked']=True;result.audit['syntax_passed']=passed
        if not passed:
            result.audit.update(status='unsupported',failure={'type':'SyntaxError','message':msg})
            atomic_bytes(a.audit,json_bytes(result.audit))
            print(f'Syntax validation failed: {msg}',file=sys.stderr)
            return 2
    write_candidate(a.output,a.audit,result)
    print(f'Candidate {a.output}, serialized instructions: {result.audit["total_serialized_instructions"]}; semantics UNVERIFIED')
    return 0

if __name__=='__main__':sys.exit(main())
