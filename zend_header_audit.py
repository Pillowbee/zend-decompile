#!/usr/bin/env python3
"""Offline, read-only comparison of supplied Zend headers with a PHP 5.2 target.

This module NEVER translates encoder keys and never marks mappings confirmed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, Any

HEADERS = ('zend_vm_opcodes.h', 'zend_vm_def.h', 'zend_compile.h')
# Features introduced long after Zend Engine 2 / PHP 5.2; strong exclusion markers.
MODERN_MARKERS = {
    'zend_vm_opcodes.h': ('ZEND_MATCH', 'ZEND_CHECK_UNDEF_ARGS', 'ZEND_INIT_PARENT_PROPERTY_HOOK_CALL'),
    'zend_vm_def.h': ('property_hook', 'ZEND_MATCH'),
    'zend_compile.h': ('zend_ast', 'zend_string', 'zend_property_hook_kind'),
}
SPECIAL = (49, 140, 199)
# These numeric definitions occur together in the PHP 5.2 family.  Their
# presence is evidence of a compatible *layout*, not a precise source release.
LEGACY_SIGNATURE = {49: 'ZEND_SWITCH_FREE', 50: 'ZEND_BRK',
                    51: 'ZEND_CONT', 57: 'ZEND_BEGIN_SILENCE',
                    58: 'ZEND_END_SILENCE', 77: 'ZEND_FE_RESET',
                    78: 'ZEND_FE_FETCH', 107: 'ZEND_CATCH',
                    108: 'ZEND_THROW', 140: 'ZEND_DECLARE_INHERITED_CLASS',
                    150: 'ZEND_USER_OPCODE'}
OPCODE = re.compile(r'^\s*#\s*define\s+(ZEND_[A-Z0-9_]+)\s+(\d+)\s*(?:$|/\*|//)',re.M)
HANDLER = re.compile(r'ZEND_VM_HANDLER\(\s*(\d+)\s*,\s*(ZEND_[A-Z0-9_]+)')


def inspect_headers(directory: Path) -> Dict[str, Any]:
    directory = Path(directory)
    files: Dict[str, Any] = {}
    missing = []
    texts = {}
    for name in HEADERS:
        p=directory/name
        if not p.is_file():
            missing.append(name)
            continue
        data=p.read_bytes()
        text=data.decode('latin1')
        texts[name]=text
        matches=[]
        for term in MODERN_MARKERS[name]:
            match=re.search(r'\b'+re.escape(term)+r'\b',text)
            if match:
                line=text.count('\n',0,match.start())+1
                matches.append({'marker':term,'line':line})
        files[name]={'sha256':hashlib.sha256(data).hexdigest(),'size':len(data),
                     'modern_markers':matches}
    numbers={}
    duplicates=[]
    if 'zend_vm_opcodes.h' in texts:
        opcode_section = texts['zend_vm_opcodes.h']
        start = opcode_section.find('#define ZEND_NOP ')
        end = opcode_section.find('#define ZEND_VM_LAST_OPCODE', start)
        # Zend Engine 2 (PHP 5.2) ends the table at EOF and has no
        # ZEND_VM_LAST_OPCODE.  The previous parser silently returned zero
        # definitions for this valid historical format.
        if start >= 0:
            opcode_section = opcode_section[start:end if end > start else len(opcode_section)]
        else:
            opcode_section = ''  # Avoid interpreting unrelated VM defines.
        for match in OPCODE.finditer(opcode_section):
            name,value=match.group(1),int(match.group(2))
            if value in numbers:
                duplicates.append({'opcode':value,'first':numbers[value]['name'],'second':name})
            numbers[value]={'name':name,'line':texts['zend_vm_opcodes.h'].count('\n',0,start+match.start())+1}
    handlers={}
    if 'zend_vm_def.h' in texts:
        for match in HANDLER.finditer(texts['zend_vm_def.h']):
            value=int(match.group(1));name=match.group(2)
            handlers.setdefault(value,[]).append({'name':name,'line':texts['zend_vm_def.h'].count('\n',0,match.start())+1})
    differences=[]
    for value in SPECIAL:
        defined=numbers.get(value)
        attached=handlers.get(value,[])
        if defined and attached and any(h['name']!=defined['name'] for h in attached):
            differences.append(value)
    all_handler_mismatches = [
        {'opcode': value, 'header': data['name'], 'handlers': [h['name'] for h in handlers[value]]}
        for value, data in sorted(numbers.items())
        if value in handlers and any(h['name'] != data['name'] for h in handlers[value])
    ]
    # Recognize the family only if independent declarations in both headers
    # match, with no duplicate numeric definitions or unsupported markers.
    legacy_layout = (
        all(numbers.get(value, {}).get('name') == name and
            any(h['name'] == name for h in handlers.get(value, []))
            for value, name in LEGACY_SIGNATURE.items())
        and 199 not in numbers and not duplicates and not all_handler_mismatches
    )
    any_modern=any(info['modern_markers'] for info in files.values())
    if missing:
        verdict='incomplete_headers'
    elif any_modern:
        verdict='incompatible_with_php_5_2'
    elif legacy_layout:
        verdict='php_5_2_family_layout_unverified_build'
    else:
        verdict='unverified_version'
    return {
        'schema_version':2,
        'target':'PHP 5.2.17 / Zend Engine 2',
        'verdict':verdict,
        'suitable_for_encoder_opcode_confirmation':False,
        'native_opcode_layout_matches_php_5_2_family':bool(legacy_layout and not any_modern and not missing),
        'exact_php_5_2_17_build_verified':False,
        'number_of_opcode_definitions':len(numbers),
        'explanation':('Observed modern Zend Engine features exclude PHP 5.2; numerical matches are not mapping evidence.'
                       if any_modern else
                       'The numeric layout matches the PHP 5.2 family, but exact 5.2.17 provenance and serialized encoder mapping remain unverified.'
                       if legacy_layout and not missing else
                       'No exact-build provenance or encoded/native per-record alignment has been established.'),
        'files':files,
        'missing':missing,
        'selected_native_opcode_numbers':{
            str(n):{'header_definition':numbers.get(n),'vm_handlers':handlers.get(n,[])} for n in SPECIAL},
        'header_internal_disagreements':differences,
        'all_header_handler_mismatches':all_handler_mismatches,
        'duplicate_numeric_definitions':duplicates,
        'encoder_map_unchanged':True,
        'status_updates':{'confirmed':0,'inferred':0,'unknown':0},
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('header_directory',type=Path)
    p.add_argument('-o','--output',type=Path)
    args=p.parse_args(argv)
    result=inspect_headers(args.header_directory)
    serialized=json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if args.output:
        args.output.write_text(serialized,encoding='utf-8')
    else:
        print(serialized,end='')
    return (2 if result['verdict'] in ('incompatible_with_php_5_2','incomplete_headers')
            else 0 if result['verdict']=='php_5_2_family_layout_unverified_build' else 1)

if __name__=='__main__':raise SystemExit(main())
