from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
import re

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

c_templ = """#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

typedef float float32_t;
typedef double float64_t;

struct {name} {{
{fields}}};

void parse_{name}({name}* out, const void* __restrict__ src) {{
    memcpy(out, src, sizeof({name}));
}}
"""

def format_c(name, fields):
    return c_templ.format_map({
        "name": name,
        "fields": f"{''.join([f'    {t}_t {n};{nl}' for t, n in fields.items()])}"
    })

py_templ = """import struct
import sys
from dataclasses import dataclass

assert sys.byteorder == "little"

raw_{name} = struct.Struct("{fmt}")

@dataclass
class {name}:
{names}
    @staticmethod
    def from_buffer(buff):
        return {name}(*raw_{name}.unpack(buff))

"""

def format_py(name, fields):
    fmt = "@" + "".join([valid_types[t][0] for t in fields])
    names = "".join([f'    {n}: {valid_types[t][1]}{nl}' for t, n in fields.items()])
    return py_templ.format_map({
        "name": name, 
        "names": names, 
        "fmt": fmt
    })

def main():
    parser = ArgumentParser()
    parser.add_argument(
        "file")
    parser.add_argument(
        "--stdout", "-s", default=False, action="store_true", help="print to stdout")
    parser.add_argument(
        "--out", "-o", type=str, default="", help="print to file")
    args, _ = parser.parse_known_args()
    fields = {}
    src = Path(args.file)
    if not ident.match(src.stem):
        raise RuntimeError(f".msg file name is not allowed: {src.name}")
    with open(src, "r") as f:
        for line in f.readlines():
            t, name = line.split()
            if not ident.match(name):
                raise RuntimeError(f"Invalid identifier: {name}")
            fields[t] = name
    c_result = format_c(src.stem, fields)
    py_result = format_py(src.stem, fields)
    if args.stdout:
        print(f"Python: {py_result}")
        print(f"C Header: {c_result}")
    if args.out:
        with open(args.out + ".h", "+w") as f:
            f.write(c_result)
        with open(args.out + ".py", "+w") as f:
            f.write(py_result)


if __name__ == "__main__": 
    main()