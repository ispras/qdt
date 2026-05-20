#!/usr/bin/env -S python3

""" Qemu Target Test Tool
"""

from common import (
    intervalmap,
    iter_trie_items,
    PortPool,
    pypath,
)
from debug import (
    DWARFInfoCache,
    InMemoryELFFile,
    RSPWatcher,
    Runtime,
    SymTab,
)

from argparse import (
    ArgumentParser,
)
from os.path import (
    abspath,
    dirname,
    isfile,
    join,
    split,
)
from subprocess import (
    PIPE,
    Popen,
)

# use ours pyrsp
with pypath("..pyrsp"):
    from pyrsp.utils import (
        wait_for_tcp_port
    )

# for config
from c2t.config import *
from debug.qrsp import *


class Q3T(object):
    "Qemu Target Test Tool configuration"

    configs = []

    def __init__(self, rsp, bins, args):
        """
@param rsp:
    A callable that returns `debug.runtime.Runtime` compatible `target`.
    E.g., a `debug.qrsp.QRSP` sub`class`.
@param bins:
    An iterable of binary files to process.
@qargs args:
    An iterable of arguments for `Popen` to run the emulator.
        """
        type(self).configs.append(self)
        self.rsp = rsp
        self.bins = list(bins)
        self.args = list(args)


port_pool = PortPool()


def build_address_map(srcmap):
    amap = intervalmap()
    for rpath, lmap in iter_trie_items(srcmap):
        for (begin_line, end_line), entries in lmap.items():
            for entry in entries:
                addr = entry.state.address
                _, end_addr = amap.interval(addr)
                amap[addr:end_addr] = (rpath, begin_line, end_line)
    return amap


class FileLinesCache(dict):

    def __missing__(self, path):
        with open(path, "r") as f:
            text = f.read()
        self[path] = lines = text.splitlines(False)
        return lines

file_lines_cache = FileLinesCache()


class ExpressionLocals(dict):

    def __init__(self, rt):
        self.rt = rt

    def __missing__(self, name):
        rt = self.rt
        try:
            val_desc = rt["name"]
        except KeyError:
            reg_idx = rt.reg_idx[name]
            val = rt.get_reg(reg_idx)
        else:
            val = val_desc.fetch()

        print("\t%s = %r" % (name, val))

        self[name] = val
        return val


def break_cb(rt, br):
    name, exprs = br
    print("hit: " + name)
    locs = ExpressionLocals(rt)
    for expr in exprs:
        print("`eval`uating %r..." % expr)
        res = eval(expr, {}, locs)
        print("\tres = %r" % res)

def main():
    ap = ArgumentParser(
        description = __doc__,
    )
    arg = ap.add_argument

    arg("config")
    arg("--ack",
        help = "set RSP `noack` to `False`",
        action = "store_true",
    )
    arg("-v", "--verbose",
        action = "store_true",
    )
    arg("-p", "--prefix",
        help = "test expression prefix",
        default = ">>>",
    )

    args = ap.parse_args()

    prefix = args.prefix
    verbose = args.verbose
    quiet = not verbose
    no_ack = not args.ack

    config_file_name = args.config
    config_dir_name = dirname(config_file_name)

    with open(config_file_name, "r") as f:
        config_src = f.read()

    config_code = compile(config_src, config_file_name, "exec")

    config_ns = dict()
    config_glob = dict(globals())
    config_glob["__file__"] = config_file_name

    exec(config_code, config_ns, config_glob)

    assert len(Q3T.configs) == 1
    config = Q3T.configs[0]

    for bin_file_name in config.bins:
        bin_file_path = bin_file_name
        if not isfile(bin_file_path):
            bin_file_path = join(config_dir_name, bin_file_name)

        print("loading %r" % bin_file_path)

        elf = InMemoryELFFile(bin_file_path)
        di = elf.get_dwarf_info()
        symtab_sect = elf.get_section_by_name(".symtab")
        symtab = SymTab(symtab_sect)
        address_map = symtab.address_map
        breakpoints = dict()
        for name, addr in address_map.items():
            if "q3t" not in name:
                continue
            breakpoints[addr] = (name, [])

        if not breakpoints:
            print("No q3t breakpoints found")
            continue

        dic = DWARFInfoCache(di,
            symtab = symtab_sect,
        )

        # account all line programms
        for cu in dic.iter_CUs():
            dic.account_line_program_CU(cu)

        addrmap = build_address_map(dic.srcmap)

        bin_file_dir, bin_file_name_only = split(bin_file_path)

        for addr, (name, exprs) in breakpoints.items():
            rpath, begin_line, end_line = addrmap[addr]
            rpath = tuple(
                (p if isinstance(p, str) else p.decode()) for p in rpath
            )
            src_path = abspath(join(bin_file_dir, *reversed(rpath)))
            print(src_path, rpath, begin_line, end_line)

            for line in file_lines_cache[src_path][begin_line:end_line]:
                i = line.find(prefix)
                if i < 0:
                    continue
                expr = line[i+3:].strip()
                exprs.append(expr)
                print(expr)

        port = port_pool.alloc_port()

        args = list(config.args)

        args_ns = dict(
            bin = bin_file_name_only,
            gdb_port = str(port),
            cwd = bin_file_dir,
        )

        args.extend(("-gdb", "tcp:localhost:{gdb_port}"))

        processed_args = []

        for arg in args:
            arg = arg.format_map(args_ns)
            processed_args.append(arg)

        if "-S" not in processed_args:
            processed_args.append("-S")

        qemu_p = Popen(processed_args,
            stdin = PIPE,
            cwd = args_ns["cwd"],
        )

        try:
            wait_for_tcp_port(port)

            rsp = config.rsp(port,
                noack = no_ack,
                verbose = verbose,
            )

            rt = Runtime(rsp, dic)

            for addr, br in breakpoints.items():
                rt.br(
                    addr,
                    lambda rt = rt, br = br: break_cb(rt, br),
                    quiet = quiet
                )

            rt.run()
        finally:
            qemu_p.terminate()
            qemu_p.wait()

if __name__ == "__main__":
    exit(main() or 0)
