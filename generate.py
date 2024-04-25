from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
import re
import struct
from typing import Iterable, List, Optional

valid_types = {
    "int8": ("b", "int"),
    "uint8": ("B", "int"),
    "int16": ("h", "int"),
    "uint16": ("H", "int"),
    "int32": ("i", "int"),
    "uint32": ("I", "int"),
    "int64": ("l", "int"),
    "uint64": ("L", "int"),
    "float32": ("f", "float"),
    "float64": ("d", "float"),
}

@dataclass
class Field:
    type: str
    name: str
    const: Optional[str]

nl = "\n"

class CTempl:
    Parse = """
    memcpy(&out->{name}, src, sizeof(out->{name}));
    src += sizeof(out->{name});"""

    Dump = """
    memcpy(buff, &obj->{name}, sizeof(obj->{name}));
    buff += sizeof(obj->{name});"""

    Main = """#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

typedef float float32_t;
typedef double float64_t;

{consts}
struct {name} {{
{fields}}};

static inline size_t parse_{name}({name}* __restrict__ out, const char* __restrict__ src, size_t size) {{
    if (size < {total_size}) return 0;{parse_fields}
    return {total_size};
}}

static inline size_t dump_{name}({name}* __restrict__ obj, char* __restrict__ buff, size_t size) {{
    if (size < {total_size}) return 0;{dump_fields}
    return {total_size};
}}
"""
    @staticmethod
    def format_consts(name, fields: Iterable[Field]):
        items = ''.join(f"    {name}_{f.name} = {f.const},{nl}" for f in fields if f.const)
        if items: return """typedef enum {{\n{}}} {}_;\n""".format(items, name)
        else: return ""
    @staticmethod
    def format(name, fields: Iterable[Field], total_size):
        return CTempl.Main.format_map({
            "name": name,
            "fields": f"{''.join(f'    {f.type}_t {f.name};{nl}' for f in fields if not f.const)}",
            "total_size": total_size,
            "parse_fields": ''.join(CTempl.Parse.format_map({"name": f.name}) for f in fields if not f.const),
            "dump_fields": ''.join(CTempl.Dump.format_map({"name": f.name}) for f in fields if not f.const),
            "consts": CTempl.format_consts(name, fields)
        })

class PyTempl:
    Main = """import struct
import sys
from dataclasses import dataclass, fields
from typing import ClassVar

@dataclass
class {name}:
{names}
    @staticmethod
    def from_buffer(buff):
        return {name}(*{name}._s.unpack(buff))
    def into_buffer(self):
        return {name}._s.pack(getattr(self, n) for n in {name}._names)

{name}._names = tuple(f.name for f in fields({name}))
{name}._s = struct.Struct("{fmt}")
        
"""
    @staticmethod
    def remap_fmt(t: str): 
        return valid_types[t][0]
    @staticmethod
    def remap_type(t: str): 
        return valid_types[t][1]
    @staticmethod
    def struct_fmt(fields: Iterable[Field]):
        return "<" + "".join(PyTempl.remap_fmt(f.type) for f in fields if not f.const)
    @staticmethod
    def format(name, fields: Iterable[Field]):
        fmt = PyTempl.struct_fmt(fields)
        names = "".join(f'    {f.name}: {PyTempl.remap_type(f.type)}{nl}' for f in fields if not f.const)
        names += "".join(f'    {f.name}: ClassVar[{PyTempl.remap_type(f.type)}] = {f.const}{nl}' for f in fields if f.const)
        return PyTempl.Main.format_map({
            "name": name, 
            "names": names, 
            "fmt": fmt
        })

def parse_line(line: str) -> Optional[Field]:
    parts = line.split()
    if len(parts) == 2:
        return Field(parts[0], parts[1], None)
    elif len(parts) == 4:
        if not parts[2] == "=": raise RuntimeError(f"Line should be [<type> <name> = <const>], was: {line}")
        return Field(parts[0], parts[1], parts[3])
    else:
        return None

def main():
    parser = ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--stdout", "-s", default=False, action="store_true", help="print to stdout")
    parser.add_argument("--out_py", type=str, default="", help="python output file")
    parser.add_argument("--out_c", type=str, default="", help="c output file")
    parser.add_argument("--name", type=str, default="", help="class name")
    args, _ = parser.parse_known_args()
    fields: List[Field] = []
    src = Path(args.file)
    if not re.match(r'([A-Za-z_][A-Za-z0-9_]*)', src.stem):
        raise RuntimeError(f".msg file name is not allowed: {src.name}")
    with open(src, "r") as f:
        for line in f.readlines():
            f = parse_line(line)
            if not f is None: 
                fields.append(f)
    name = args.name or src.stem
    c_result = CTempl.format(name, fields, struct.calcsize(PyTempl.struct_fmt(fields)))
    py_result = PyTempl.format(name, fields)
    if args.stdout:
        print(f"Python: ---\n\n{py_result}\n\n")
        print(f"C Header: ---\n\n{c_result}\n\n")
    def do_open(path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return open(p, "+w")
    if args.out_c:
        with do_open(args.out_c) as f:
            f.write(c_result)
    if args.out_py:
        with do_open(args.out_py) as f:
            f.write(py_result)


if __name__ == "__main__": 
    main()
