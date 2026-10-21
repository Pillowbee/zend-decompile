#!/usr/bin/env python3
"""Safe batch processing: no source execution, fail closed, atomic artifacts."""
from __future__ import annotations
from pathlib import Path
import hashlib, json, os, subprocess, tempfile
from .engine import restore_result, RestoreResult, __version__
from .partial import partial_text

def json_bytes(value: dict) -> bytes:
    return (json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode('utf8')

def atomic_bytes(path: Path, data: bytes, *, refuse_overwrite: bool = True) -> None:
    """Same-filesystem temp + replace; refuses overwriting output by default."""
    path.parent.mkdir(parents=True,exist_ok=True)
    if refuse_overwrite and path.exists():
        raise FileExistsError(f'Output exists: {path}')
    name=None
    try:
        with tempfile.NamedTemporaryFile(prefix='.tmp_',dir=path.parent,delete=False) as f:
            name=Path(f.name); f.write(data); f.flush(); os.fsync(f.fileno())
        if refuse_overwrite and path.exists():raise FileExistsError(f'Output exists: {path}')
        os.replace(name,path)
    finally:
        if name is not None and name.exists():name.unlink()

def write_candidate(out: Path, audit_path: Path, result: RestoreResult) -> None:
    if result.status!='candidate_generated' or result.code is None:raise ValueError('No complete candidate')
    if out.exists() or audit_path.exists():raise FileExistsError('Refusing to overwrite existing candidate or audit')
    if out.resolve()==audit_path.resolve():raise ValueError('Code and audit paths overlap')
    # Stage both; audit first, code second. Roll back newly created audit on failure.
    atomic_bytes(audit_path,json_bytes(result.audit))
    try:
        atomic_bytes(out,result.code)
    except BaseException:
        audit_path.unlink(missing_ok=True)
        raise

def syntax_check(code: bytes, linter: Path, *, library_dir: Path|None=None) -> tuple[bool,str]:
    env=os.environ.copy()
    if library_dir:
        env['LD_LIBRARY_PATH']=str(library_dir)+((':'+env['LD_LIBRARY_PATH']) if env.get('LD_LIBRARY_PATH') else '')
    with tempfile.NamedTemporaryFile(suffix='.php') as file:
        file.write(code);file.flush()
        proc=subprocess.run([str(linter),'-n','-l',file.name],capture_output=True,timeout=20,env=env)
    return proc.returncode==0,(proc.stdout+proc.stderr).decode('utf8','replace')[:1500]

def _partial_report(path:Path,row:dict,result:RestoreResult) -> bytes:
    """Non-executable diagnostics: no PHP tags, extensions .txt only."""
    groups=result.audit.get('group_diagnostics',[])
    lines=['/* UNRECOVERED */','Zend Decompiler diagnostic ONLY; NOT runnable PHP.',
        f"Input: {row['source']}",f"Failure: {result.reason}"]
    for g in groups:
        lines += [f"GROUP {g['name']}: mapped={g['mapped']}/{g['instructions']}; unknown={g['unknown_indices']}",
                  '/* UNRECOVERED */']
    return ('\n'.join(lines)+'\n').encode('utf8')

def batch(source:Path, output:Path, dictionary:Path, mapping:Path, recursive:bool=False,
          php_linter:Path|None=None, lib_dir:Path|None=None, isolate_parser:bool=False) -> dict:
    if source.is_file():inputs=[source];root=source.parent
    elif source.is_dir():
        root=source;inputs=sorted(x for x in (source.rglob('*.php') if recursive else source.glob('*.php')) if x.is_file() and not x.is_symlink())
    else:raise ValueError('Input not found')
    if not inputs:raise ValueError('No PHP input files')
    if output.resolve()==root.resolve() or output.resolve().is_relative_to(root.resolve()):
        raise ValueError('Output directory must not be inside input directory')
    output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for path in inputs:
        rel=path.relative_to(root)
        row={'source':str(rel),'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
             'status':'unsupported','semantic_equivalence_proven':False}
        res=restore_result(path,dictionary,mapping,isolate_parser=isolate_parser)
        row['status']=res.status
        if 'recognition_fraction' in res.audit:
            row['opcode_recognition_fraction']=res.audit['recognition_fraction']
            row['mapped_instructions']=res.audit['mapped_instructions']
            row['serialized_instructions']=res.audit['serialized_instructions']
            row['unknown_windows']=res.audit.get('unknown_windows',[])
            row['group_coverage']=[{'name':g['name'],'instructions':g['instructions'],
                'mapped':g['mapped'],'recognition_fraction':g['recognition_fraction'],
                'confirmed_instruction_count':g['confirmed_instruction_count'],
                'confirmed_fraction':g['confirmed_fraction']}
                for g in res.audit.get('group_diagnostics',[])]
        if res.status=='candidate_generated':
            if php_linter:
                try:passed,msg=syntax_check(res.code,php_linter,library_dir=lib_dir)
                except Exception as exc:passed=False;msg=f'PHP syntax verifier failed: {exc}'
                res.audit['syntax_checked']=True
                res.audit['syntax_passed']=passed
                row['syntax_checked']=True;row['syntax_passed']=passed
                if not passed:
                    row['status']='unsupported';row['reason']='Syntax check unsuccessful: '+msg[:500]
            if row['status']=='candidate_generated':
                dst=output/rel;adst=output/'_audits'/rel.with_suffix('.json')
                try:
                    write_candidate(dst,adst,res)
                    row.update(output=str(dst.relative_to(output)),audit=str(adst.relative_to(output)))
                except Exception as exc:
                    row['status']='unsupported';row['reason']=f'{type(exc).__name__}: {exc}'[:800]
        elif res.status=='unsupported':
            row['reason']=res.reason
        if res.audit.get('failure'):
            row['failure_context']=res.audit['failure']
        if row['status']=='unsupported':
            partial=output/'_partial_READ_ONLY'/rel.with_suffix('.txt')
            try:
                content=_partial_report(path,row,res)
                if res.audit.get('group_diagnostics'):
                    try:
                        research_txt,research_report=partial_text(path,dictionary,mapping)
                        content=research_txt
                        row['recoverable_groups']=research_report['complete_groups']
                        row['total_groups']=len(research_report['groups'])
                        row['recoverable_group_fraction']=(research_report['complete_groups']/len(research_report['groups']) if research_report['groups'] else 1.0)
                    except Exception as sub_exc:
                        row['partial_analysis_error']=f'{type(sub_exc).__name__}: {sub_exc}'[:400]
                atomic_bytes(partial,content,refuse_overwrite=True)
                row['partial_diagnostic']=str(partial.relative_to(output))
            except Exception as exc:
                row['partial_error']=f'{type(exc).__name__}: {exc}'[:300]
        if row['status']!='candidate_generated':
            adst=output/'_audits'/rel.with_suffix('.json')
            try:
                if res.audit.get('status')!=row['status']:
                    res.audit['status']=row['status']
                    res.audit['failure']={'type':'BatchValidation','message':row.get('reason','Rejected in batch')}
                atomic_bytes(adst,json_bytes(res.audit),refuse_overwrite=True)
                row['audit']=str(adst.relative_to(output))
            except Exception as exc:
                row['audit_error']=f'{type(exc).__name__}: {exc}'[:400]
        rows.append(row)
    report={'version':__version__,'total':len(rows),
        'generated':sum(r['status']=='candidate_generated' for r in rows),
        'unsupported':sum(r['status']=='unsupported' for r in rows),
        'not_encoded':sum(r['status']=='not_encoded' for r in rows),
        'round_trip':{'status':'not_run','reason':'Native compile-only probe exists but no verified native-oparray to SSG Team serializer adapter'},
        'semantic_equivalence_proven':False,'files':rows}
    atomic_bytes(output/'batch_report.json',json_bytes(report),refuse_overwrite=True)
    return report
