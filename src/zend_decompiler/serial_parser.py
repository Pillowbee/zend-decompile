#!/usr/bin/env python3
"""Offline, *partial* reader for this Zend Encoder 2002-era serialized stream.

Does not execute PHP or load Zend Optimizer. Parses fields confirmed on the supplied
header_index.php and basket.php samples. Opcode byte uses an 8-position substitution:
optional `--opcode-map` is an observation-based map, NOT a universal decoder.

Research prototype. It validates lengths and boundaries; unknown zval tags fail closed.
"""
from __future__ import annotations
import argparse
import json
import zlib
from dataclasses import dataclass
from pathlib import Path

MAX_BINARY = 64 * 1024 * 1024
MAX_INSTRUCTIONS = 150_000
MAX_VARS = 100_000
MAX_STRING = 16 * 1024 * 1024

class FormatError(ValueError):
    pass

@dataclass
class Reader:
    data: bytes
    pos: int = 0

    def read(self, n: int) -> bytes:
        if n < 0 or n > MAX_STRING or self.pos + n > len(self.data):
            raise FormatError(f'Cannot read {n} bytes at 0x{self.pos:X}')
        r = self.data[self.pos:self.pos+n]
        self.pos += n
        return r

    def byte(self) -> int:
        return self.read(1)[0]

    def num(self) -> int:
        start = self.pos
        n = self.byte()
        if not (2 <= n <= 24):
            raise FormatError(f'Invalid ASCII-integer field length {n} at 0x{start:X}')
        body = self.read(n)
        if body[-1:] != b'\0' or not body[:-1].lstrip(b'-').isdigit():
            raise FormatError(f'Invalid ASCII-integer encoding at 0x{start:X}: {body!r}')
        return int(body[:-1])

    def sized(self) -> bytes:
        return self.read(self.num())

    def node(self) -> dict:
        start = self.pos
        typ = self.byte()
        if typ == 1:
            ztag = self.byte()
            refcount = self.num()
            is_ref = self.byte()
            if ztag == 3:  # serialized string tag
                raw = self.sized()
                value = {'kind':'string', 'raw_hex':raw.hex(), 'length':len(raw)}
            elif ztag == 1:  # serialized integer tag
                value = {'kind':'integer', 'value':self.num()}
            elif ztag == 0:  # NULL, no payload
                value = {'kind':'null'}
            else:
                raise FormatError(f'Unsupported serialized constant tag {ztag} at 0x{start:X}')
            return {'type':typ,'constant_tag':ztag,'refcount':refcount,
                    'is_ref_flag':is_ref,'constant':value}
        if typ not in (2,4,8,16):
            raise FormatError(f'Unsupported operand type {typ} at 0x{start:X}')
        lo,hi = self.num(),self.num()
        return {'type':typ,'word0':lo,'word1':hi}

    def opcodes(self, count: int, map_: dict) -> list[dict]:
        if count < 0 or count > MAX_INSTRUCTIONS:
            raise FormatError(f'Invalid instruction count {count}')
        ops = []
        for i in range(count):
            start = self.pos
            ob = self.byte()
            result,op1,op2 = self.node(),self.node(),self.node()
            extended, line = self.num(), self.num()
            key = f'{i%8}:{ob}'
            ops.append({'index':i,'offset':start,'size':self.pos-start,
                        'encoded_opcode':ob,'decoded_opcode':map_.get(key),
                        'result':result,'op1':op1,'op2':op2,
                        'extended_value':extended,'line':line})
        return ops

    def trailer(self) -> dict:
        n = self.num()
        if not (0 <= n <= MAX_VARS):raise FormatError('Invalid break/continue count')
        jumps = [{'start':self.num(),'cont':self.num(),'parent':self.num()}
                 for _ in range(n)]
        flags = self.read(3)
        n = self.num()
        if not (0<=n<=MAX_VARS):raise FormatError('Invalid CV count')
        cvs=[]
        for i in range(n):
            val = self.sized()
            cvs.append({'index':i,'name_hex':val.hex(),'hash_signed':self.num()})
        return {'loop_records':jumps,'trailing_flags_hex':flags.hex(),'compiled_vars':cvs}


def parse_binary(raw: bytes, opcode_map: dict | None = None) -> dict:
    if len(raw)>MAX_BINARY:raise FormatError('Binary stream exceeds limit')
    p=Reader(raw);opcode_map=opcode_map or {}
    banner=p.sized()
    if banner!=b'SSG Team':raise FormatError(f'Unexpected signature: {banner[:32]!r}')
    fields=[p.num() for _ in range(6)]
    delimiter=p.byte()
    identifier=p.sized()
    property_=p.num()
    # Some files register named global symbols in the header. Each record is
    # a length-prefixed name followed by a signed decimal hash.
    if not (0 <= property_ <= MAX_VARS):
        raise FormatError(f"Invalid globals count {property_}")
    header_symbols = []
    for i in range(property_):
        raw_name = p.sized()
        header_symbols.append({"index": i, "name_hex": raw_name.hex(), "hash_signed": p.num()})
    marker=p.byte()
    numeric_flag=p.num()
    flags=p.read(2)
    count=p.num()
    duplicate_count=p.num()
    last_tmp=p.num()
    if duplicate_count != count:raise FormatError(f'Instruction counts differ: {count} vs {duplicate_count}')
    main={'serialized_count':count,'temporary_slots':last_tmp,
          'opcodes':p.opcodes(count,opcode_map)}
    main.update(p.trailer())
    count_functions=p.num()
    if count_functions<0 or count_functions>1000:raise FormatError('Invalid function count')
    functions=[]
    for _ in range(count_functions):
        tag=p.byte()
        nul_name=p.sized()
        if not nul_name.endswith(b'\0'):raise FormatError('Function table name lacks NUL')
        type_=p.byte()
        count_unknown=p.num()
        auxflag=p.byte()
        name=p.sized()
        null=p.byte()
        if null != 0:raise FormatError('Function name terminator missing')
        opcount=p.num(); duplicate=p.num();temps=p.num()
        if duplicate!=opcount:raise FormatError('Function opcode counts differ')
        obj={'name_hex':name.hex(),'tag':tag,'kind':type_,
             'function_param':count_unknown,'auxflag':auxflag,
             'serialized_count':opcount,'temporary_slots':temps,
             'opcodes':p.opcodes(opcount,opcode_map)}
        obj.update(p.trailer());functions.append(obj)
    # Present in both supplied samples; interpretation not yet established.
    last_fields=[]
    while p.pos<len(raw):
        last_fields.append(p.num())
        if len(last_fields)>16:raise FormatError('Unexpected long tail')
    return {'format':'zend-encoder-serialized-research-v6',
            'input_size':len(raw),'banner':banner.decode('ascii'),
            'header_fields':fields, 'header_delimiter':delimiter,
            'header_identifier_hex':identifier.hex(), 'property':property_, 'header_symbols':header_symbols,
            'marker':marker,'numeric_flag':numeric_flag,'header_flags_hex':flags.hex(),
            'main':main,'functions':functions,'tail_numbers':last_fields,
            'consumed_bytes':p.pos}


def decompress_encoded(source: Path, dictionary: bytes) -> list[tuple[int,bytes]]:
    buf=source.read_bytes()
    if len(buf)>MAX_BINARY:raise FormatError('Encoded file exceeds limit')
    checksum=zlib.adler32(dictionary)
    found=[]
    for idx in range(len(buf)-6):
        cmf,flg=buf[idx:idx+2]
        if (cmf & 15)!=8 or (cmf>>4)>7 or ((cmf<<8)+flg)%31!=0 or not (flg&0x20):continue
        if int.from_bytes(buf[idx+2:idx+6], 'big') != checksum:continue
        dec=zlib.decompressobj(zdict=dictionary)
        try:
            output=dec.decompress(buf[idx:], MAX_BINARY+1)
        except zlib.error as exc:
            raise FormatError(f'Invalid zlib stream at 0x{idx:X}: {exc}') from exc
        if len(output)>MAX_BINARY or not dec.eof:
            raise FormatError(f'Invalid/incomplete zlib stream at 0x{idx:X}')
        found.append((idx,output))
    return found


def disassembly(parsed: dict, names: dict[str,str]) -> str:
    """Observational disassembly; unknown instructions and relocations stay unknown."""
    out=[]
    for name,g in [('<main>',parsed['main'])]+[
        (bytes.fromhex(f['name_hex']).decode('latin1'),f) for f in parsed['functions']]:
        out.append(f'FUNCTION {name} [serialized instructions: {len(g["opcodes"])}]')
        vars_={v['index']:bytes.fromhex(v['name_hex']).decode('cp1251',errors='replace')
               for v in g['compiled_vars']}
        for op in g['opcodes']:
            opcode=op['decoded_opcode']
            label=names.get(str(opcode),f'unknown(raw=0x{op["encoded_opcode"]:02x})') if opcode is not None else f'unknown(raw=0x{op["encoded_opcode"]:02x})'
            desc=[]
            for key in ('result','op1','op2'):
                node=op[key]
                if node['type']==1:
                    v=node['constant']
                    if v['kind']=='string':
                        x=bytes.fromhex(v['raw_hex']).decode('cp1251',errors='replace')
                        val=repr(x)
                    elif v['kind']=='null':val='NULL'
                    else:val=str(v['value'])
                elif node['type']==16:
                    val='$'+vars_.get(node['word0'],f'CV[{node["word0"]}]')
                else:
                    val=f't{node["type"]}[{node["word0"]}:{node["word1"]}]'
                desc.append(f'{key}={val}')
            out.append(f"  #{op['index']:03d} L{op['line']:03d} {label:<25} {' '.join(desc)} ext={op['extended_value']}")
        out.append('')
    return '\n'.join(out)


def summary(parsed: dict) -> str:
    groups=[('<main>',parsed['main'])]+[
        (bytes.fromhex(f['name_hex']).decode('latin1'),f) for f in parsed['functions']]
    out=['# Автономный разбор сериализации Zend Encoder', '',
         f"Обработано байтов: {parsed['consumed_bytes']} / {parsed['input_size']}",
         f"Строка идентификации: `{parsed['banner']}`", '',
         '| Блок | Записей опкодов | CV | Таблицы циклов | Распознано типов опкодов |',
         '|---|---:|---:|---:|---:|']
    for name,g in groups:
        known=sum(x['decoded_opcode'] is not None for x in g['opcodes'])
        out.append(f"| `{name}` | {len(g['opcodes'])} | {len(g['compiled_vars'])} | {len(g['loop_records'])} | {known} |")
    out+=['','## Имена переменных','']
    for name,g in groups:
        out.append(f'### {name}')
        out.extend(f"- CV[{v['index']}] = `${bytes.fromhex(v['name_hex']).decode('cp1251', errors='replace')}`" for v in g['compiled_vars'])
        if not g['compiled_vars']:out.append('Нет именованных переменных')
        out.append('')
    out+=['**Ограничение:** присутствующие номера опкодов получены из эмпирической таблицы соответствий. '
          'Неизвестные записи остаются без номера. Парсер пока не реконструирует произвольный PHP-код и '
          'не воспроизводит все внутренние смещения Zend Engine.']
    return '\n'.join(out)+'\n'


def recover_include_only(parsed: dict, *, encoding: str = 'cp1251') -> str:
    """Strictly limited reconstruction for scripts containing includes and RETURN 1.

    Not a generic PHP decompiler; refuses any unexpected instruction.
    """
    if parsed['functions']:
        raise FormatError('Include-only recovery does not support declared functions')
    ops=parsed['main']['opcodes']
    if len(ops)<2:
        raise FormatError('Not an include-only op_array')
    body=[]
    for op in ops[:-1]:
        if op['decoded_opcode'] != 73:  # PHP 5.2 ZEND_INCLUDE_OR_EVAL
            raise FormatError(f"Instruction #{op['index']} is not a confirmed INCLUDE_OR_EVAL")
        cv = op['op1'].get('constant')
        if not cv or cv['kind'] != 'string':
            raise FormatError('Include target is not a literal string')
        flag=op['op2']
        if flag['type'] != 8 or flag['word0'] not in (2,4):
            raise FormatError('Include type is not include or include_once')
        string=bytes.fromhex(cv['raw_hex']).decode(encoding)
        # PHP single-quoted literal escaping (only backslash and quote).
        quoted = string.replace('\\','\\\\').replace("'","\\'")
        action = 'include_once' if flag['word0']==4 else 'include'
        body.append(f"{action} '{quoted}';")
    ret=ops[-1]
    if (ret['decoded_opcode'] != 62 or ret['op1'].get('constant') != {'kind':'integer','value':1}):
        raise FormatError('Expected a final RETURN 1')
    return '<?php\n' + '\n'.join(body) + '\n'


def main_cli():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path,help='.zend.bin or an encoded .php')
    p.add_argument('--dictionary',type=Path,help='Required only for encoded PHP files')
    p.add_argument('--opcode-map',type=Path,help='Optional *observed* substitution table')
    p.add_argument('--out',required=True,type=Path,help='JSON output file')
    p.add_argument('--recover-includes',type=Path,help='Optional strict include-only PHP recovery')
    args=p.parse_args()
    mp={}; names={}
    if args.opcode_map:
        lookup=json.loads(args.opcode_map.read_text())
        mp=lookup['opcodes']; names=lookup.get('names',{})
    if args.input.suffix.lower()=='.bin': streams=[(0,args.input.read_bytes())]
    else:
        if args.dictionary is None:p.error('--dictionary required for a PHP file')
        streams=decompress_encoded(args.input,args.dictionary.read_bytes())
        if not streams:raise SystemExit('No matching zlib streams found')
    results=[]
    for off,raw in streams:
        record=parse_binary(raw,mp)
        record['compressed_offset']=off
        results.append(record)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    report='\n\n'.join(summary(x) for x in results)
    args.out.with_suffix('.md').write_text(report)
    args.out.with_suffix('.txt').write_text('\n'.join(disassembly(r,names) for r in results))
    if args.recover_includes:
        if len(results)!=1:raise FormatError('Include-only recovery requires exactly one data stream')
        php = recover_include_only(results[0])
        args.recover_includes.parent.mkdir(parents=True,exist_ok=True)
        args.recover_includes.write_text(php, encoding='cp1251')
        print(f'Include-only PHP recovered: {args.recover_includes}')
    print(f'OK: {len(results)} stream(s) parsed, {sum(r["consumed_bytes"] for r in results)} bytes.')
    for r in results:
        print(f'  main={len(r["main"]["opcodes"])} serialized opcodes, '+
              f'{len(r["functions"])} functions, '+
              f'{sum(len(f["opcodes"]) for f in r["functions"])} function opcodes')
    print(f'Files: {args.out} and {args.out.with_suffix(".md")}')

if __name__=='__main__':main_cli()
