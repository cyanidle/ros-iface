from argparse import ArgumentParser
from pathlib import Path
import re
import struct

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

ident = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
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

struct {name} {{
{fields}}};

static inline size_t parse_{name}({name}* out, const char* __restrict__ src, size_t size) {{
    if (size < {total_size}) return 0;{parse_fields}
    return {total_size};
}}
static inline size_t dump_{name}({name}* obj, char* __restrict__ buff, size_t size) {{
    if (size < {total_size}) return 0;{dump_fields}
    return {total_size};
}}
"""
    @staticmethod
    def format(name, fields, total_size):
        return CTempl.Main.format_map({
            "name": name,
            "fields": f"{''.join(f'    {t}_t {n};{nl}' for n, t in fields)}",
            "total_size": total_size,
            "parse_fields": ''.join(CTempl.Parse.format_map({
                "name": n
            }) for n, t in fields),
            "dump_fields": ''.join(CTempl.Dump.format_map({
                "name": n
            }) for n, t in fields)
        })

class PyTempl:
    Main = """import struct
import sys
from dataclasses import dataclass, fields

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
    def struct_fmt(fields):
        return "<" + "".join([valid_types[t][0] for n, t in fields])
    @staticmethod
    def format(name, fields):
        fmt = PyTempl.struct_fmt(fields)
        names = "".join([f'    {n}: {valid_types[t][1]}{nl}' for n, t in fields])
        return PyTempl.Main.format_map({
            "name": name, 
            "names": names, 
            "fmt": fmt
        })

def main():
    parser = ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--stdout", "-s", default=False, action="store_true", help="print to stdout")
    parser.add_argument("--out_py", type=str, default="", help="python output file")
    parser.add_argument("--out_c", type=str, default="", help="c output file")
    args, _ = parser.parse_known_args()
    fields = []
    src = Path(args.file)
    if not ident.match(src.stem):
        raise RuntimeError(f".msg file name is not allowed: {src.name}")
    with open(src, "r") as f:
        for line in f.readlines():
            t, name = line.split()
            if not ident.match(name):
                raise RuntimeError(f"Invalid identifier: {name}")
            fields.append((name, t))
    c_result = CTempl.format(src.stem, fields, struct.calcsize(PyTempl.struct_fmt(fields)))
    py_result = PyTempl.format(src.stem, fields)
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
