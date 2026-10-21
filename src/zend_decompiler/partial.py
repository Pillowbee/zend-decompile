"""Per-function research in a disposable directory; export TEXT ONLY.

Function fragments are EXPERIMENTAL, unverified, and never exported as .php.
"""
from __future__ import annotations
from pathlib import Path
import tempfile
from .research import research


def partial_text(source:Path,dictionary:Path,mapping:Path) -> tuple[bytes,dict]:
    with tempfile.TemporaryDirectory(prefix='zend_research_') as folder:
        root=Path(folder)
        report=research(source,dictionary,mapping,root)
        lines=['/* UNRECOVERED */','INCOMPLETE SOURCE — NON-EXECUTABLE TEXT DOCUMENT ONLY.',
            f'File: {source.name}',
            f"Recovered {report['complete_groups']} of {len(report['groups'])} code groups; semantics NOT verified.",'']
        fragments=root/(source.stem+'_validated_fragments')
        for row in report['groups']:
            name=row['name']
            lines.append(f'=== {name} | {row["serialized_instructions"]} instructions | {"CANDIDATE FRAGMENT" if row["generated"] else "UNRECOVERED"} ===')
            if row['generated']:
                target=(root/'main_fragment_READ_ONLY.txt') if name=='<main>' else fragments/(name+'.php')
                if target.exists():
                    # Human-readable fragment; opening PHP tag stripped. File extension .txt.
                    content=target.read_bytes().decode('cp1251','replace').replace('<?php','[PHP OPEN TAG OMITTED]')
                    lines.extend([content,'This candidate group has NOT been behaviorally verified.'])
                else:lines.append('No separate code fragment available.')
            else:
                lines.append('/* UNRECOVERED */')
                lines.append('Reason: '+row.get('failure','Unspecified unsupported construction'))
            lines.append('')
        return ('\n'.join(lines)+'\n').encode('utf8'),report
