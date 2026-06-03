#!/usr/bin/env -S python3

""" Qemu Target Test Tool
"""

from common import (
    CLICoDispatcher,
    intervalmap,
    iter_trie_items,
    PortPool,
    pypath,
)
from debug import (
    DWARFInfoCache,
    InMemoryELFFile,
    Runtime,
    SymTab,
)

from argparse import (
    ArgumentParser,
)
from functools import (
    wraps,
)
from os.path import (
    abspath,
    dirname,
    isfile,
    join,
    split,
)
from struct import (
    pack,
    unpack,
)
from subprocess import (
    PIPE,
    Popen,
)
from time import (
    time,
)
from traceback import (
    format_exc,
)

# use ours pyrsp
with pypath("..pyrsp"):
    from pyrsp.utils import (
        QMP,
        wait_for_tcp_port,
    )

# for config
from c2t.config import *
from debug.qrsp import *


def q3t_u2f(u):
    return unpack("f", pack("I", u))[0]

def q3t_f2u(f):
    return unpack("I", pack("f", f))[0]

def q3t_u2d(u):
    return unpack("d", pack("Q", u))[0]

def q3t_d2u(d):
    return unpack("Q", pack("d", d))[0]

def q3t_join_be(*uu, **kw):
    shift = kw.pop("shift", 32)
    res = 0
    for u in uu:
        res <<= shift
        res |= u
    return res

def q3t_join_le(*uu, **kw):
    return q3t_join_be(*reversed(uu), **kw)

def q3t_iter_le(u, shift = 32):
    mask = (1 << shift) - 1
    while u:
        yield u & mask
        u >>= shift

def q3t_le(*a, **kw):
    return tuple(q3t_iter_le(*a, **kw))

def q3t_iter_be(*a, **kw):
    return reversed(tuple(q3t_iter_le(*a, **kw)))

def q3t_be(*a, **kw):
    return tuple(q3t_iter_be(*a, **kw))


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
    It must define an option to load a target code from file {bin}.
    E.g., `"-kernel", "{bin}"`.
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


def format_val(val):
    if isinstance(val, int):
        val_str = "%d %u 0x%x" % (val, val, val)
    else:
        val_str = repr(val)
    return val_str

def print_val(name, val):
    print("\t%s: %s" % (name, format_val(val)))


class ExpressionLocals(dict):

    def __init__(self, br, verbose = False):
        self.br = br
        self.verbose = verbose

    def __missing__(self, name):
        ts = self.br.ts
        rt = ts.rt
        try:
            val_desc = rt[name]
        except KeyError:
            try:
                reg_idx = rt.reg_idx[name]
            except KeyError:
                raise
            else:
                val = rt.get_reg(reg_idx)
        else:
            val = val_desc.fetch()

        if self.verbose:
            print_val(name, val)

        self[name] = val
        return val


class Q3TBreakpoint(object):

    def __init__(self, ts, name, addr):
        self.ts = ts
        self.addr = addr
        self.name = name
        self.exprs = []

    def __call__(self):
        ts = self.ts
        ts.t_last_br = time()
        verbose = ts.verbose
        if verbose:
            print("hit: " + self.name)
        locs = ExpressionLocals(self, verbose = verbose)
        for expr in self.exprs:
            if verbose:
                print("`eval`uating %r..." % expr)
            try:
                res = eval(expr, ts.namespace, locs)
            except:
                print(format_exc())
                res = False
            # If `verbose`, values are already printed by `ExpressionLocals`.
            if not res:
                ts.fail(locs)
                if not verbose:
                    for name, val in sorted(locs.items()):
                        print_val(name, val)
            if verbose or not res:
                print("\tres: %r" % res)

            ts.t_last_br = time()


def is_q3t_name(n):
    return n.startswith("q3t")

def only_q3t_items(ii):
    for i in ii:
        if is_q3t_name(i[0]):
            yield i


def gen_callable_verbose_wrapper(n, v):
    @wraps(v)
    def wrapper(*a, **kw):
        ret = v(*a, **kw)
        print("\t%s(...): " % (n,) + format_val(ret))
        return ret
    return wrapper


class Q3TTestState(object):

    rt = None
    qmp = None

    def __init__(self, timeout = 5.0, verbose = False):
        self.working = True
        self.verbose = verbose
        self.failures = []
        self.timed_out = False
        self.t_last_br = None
        self.timeout = timeout
        self.namespace = {}
        self.update_namespace(only_q3t_items(globals().items()))
        self.update_namespace(__builtins__.__dict__.items(), wrap = False)
        self.update_namespace(
            (n, getattr(self, n)) for n in dir(self) if is_q3t_name(n)
        )

    def update_namespace(self, data, wrap = True):
        ns = self.namespace
        if wrap and self.verbose:
            func_t = type(only_q3t_items)
            method_t = type(self.q3t_quit)
            callable_tt = (func_t, method_t)

            for n, v in tuple(dict(data).items()):
                if is_q3t_name(n) and isinstance(v, callable_tt):
                    v = gen_callable_verbose_wrapper(n, v)
                ns[n] = v
        else:
            ns.update(data)

    @property
    def result(self):
        if self.failures:
            return "FAILED"
        if self.timed_out:
            return "TIMEOUT"
        return "PASSED"

    def q3t_quit(self):
        self.working = False
        self.rt.exit()
        return True

    def q3t_set(self, *pairs, **kw):
        kw.update(pairs)
        target = self.rt.target
        regs = target.regs
        ns = self.namespace
        for n, v in kw.items():
            if n in regs:
                target.set_reg(n, v)
            else:
                ns[n] = v
        return True

    def q3t_ld(self, addr, size):
        return self.rt.target.dump(size, addr)

    def fail(self, locs):
        # locs (`ExpressionLocals`) has reference to `Q3TBreakpoint`
        self.working = False
        self.rt.exit()
        self.failures.append(locs)

    def co_main(self):
        if self.t_last_br is None:
            self.t_last_br = time()
        while self.working:
            t = time()
            dt = t - self.t_last_br
            if dt > self.timeout:
                self.rt.exit()
                self.qmp("stop")
                self.timed_out = True

            if self.result != "PASSED":
                break

            yield False

        print("result: " + self.result)

AUTO_EXPRS = tuple(dict(
    q3t_quit = "q3t_quit()",
).items())


def main():
    ap = ArgumentParser(
        description = __doc__,
    )
    arg = ap.add_argument

    arg("config",
        help = "Python script instantiating `Q3T`"
    )
    arg("--ack",
        help = "set RSP `noack` to `False`",
        action = "store_true",
    )
    arg("-v", "--verbose",
        action = "count",
        default = 1,
        help = "+1 to verbocity; 1: more q3t messages, 2: + rsp messages"
    )
    arg("-q", "--quiet",
        action = "count",
        default = 0,
        help = "-1 to verbocity"
    )
    arg("-p", "--prefix",
        help = "test expression prefix",
        default = ">>>",
    )
    arg("-t", "--timeout",
        default = 5.0,
        type = float,
        help = "stop the emulator if no breakpoints hit during timeout",
    )

    args = ap.parse_args()

    prefix = args.prefix
    verbose = args.verbose - args.quiet
    quiet = verbose < 2
    no_ack = not args.ack
    timeout = args.timeout

    config_file_name = abspath(args.config)
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

    exit_code = 0

    for bin_file_name in config.bins:
        bin_file_path = bin_file_name
        if not isfile(bin_file_path):
            bin_file_path = join(config_dir_name, bin_file_name)
        if not isfile(bin_file_path):
            print("no such file %r" % bin_file_path)
            continue

        bin_file_path = abspath(bin_file_path)

        ts = Q3TTestState(verbose = verbose, timeout = timeout)

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
            breakpoints[addr] = Q3TBreakpoint(ts, name, addr)

        if breakpoints:
            print("q3t breakpoint(s) found: " + str(len(breakpoints)))
        else:
            print("No q3t breakpoint(s) found")
            continue

        ts.update_namespace(address_map)

        disp = CLICoDispatcher()

        dic = DWARFInfoCache(di,
            symtab = symtab_sect,
        )

        # account all line programms
        for cu in dic.iter_CUs():
            dic.account_line_program_CU(cu)

        addrmap = build_address_map(dic.srcmap)

        bin_file_dir, bin_file_name_only = split(bin_file_path)

        for addr, br in breakpoints.items():
            name = br.name
            append_expr = br.exprs.append

            rpath, begin_line, end_line = addrmap[addr]
            rpath = tuple(
                (p if isinstance(p, str) else p.decode()) for p in rpath
            )
            src_path = abspath(join(bin_file_dir, *reversed(rpath)))
            if verbose:
                print("%s at %r %u:%u" % (
                    name,
                    src_path,
                    begin_line,
                    end_line,
                ))

            for line in file_lines_cache[src_path][begin_line:end_line]:
                i = line.find(prefix)
                if i < 0:
                    continue
                expr = line[i+3:].strip()
                append_expr(expr)
                if verbose:
                    print("\t%r" % expr)

            for infix, expr in AUTO_EXPRS:
                if infix in name:
                    append_expr(expr)
                    if verbose:
                        print("\t%r (auto)" % expr)

            if verbose and not br.exprs:
                print("\tno expressions")

        gdb_port = port_pool.alloc_port()
        if verbose:
            print("gdb_port: " + str(gdb_port))
        qmp_port = port_pool.alloc_port()
        if verbose:
            print("qmp_port: " + str(qmp_port))

        emu_args = list(config.args)

        args_ns = dict(
            bin = bin_file_name_only,
            gdb_port = str(gdb_port),
            cwd = bin_file_dir,
            qmp_port = str(qmp_port),
        )

        emu_args.extend(("-gdb", "tcp:localhost:{gdb_port},nowait"))
        emu_args.extend(("-qmp", "tcp:localhost:{qmp_port},server,nowait"))

        final_emu_args = []

        for arg in emu_args:
            arg = arg.format_map(args_ns)
            final_emu_args.append(arg)

        if "-S" not in final_emu_args:
            final_emu_args.append("-S")

        print("starting emulator...")
        if verbose:
            print("\n\t".join(repr(a) for a in final_emu_args))

        emu_p = Popen(final_emu_args,
            stdin = PIPE,
            cwd = args_ns["cwd"],
        )

        if verbose:
            print("pid: " + str(emu_p.pid))

        try:
            wait_for_tcp_port(qmp_port)

            qmp = QMP(qmp_port)
            ts.qmp = qmp

            wait_for_tcp_port(gdb_port)

            rsp = config.rsp(gdb_port,
                noack = no_ack,
                verbose = verbose > 1,
            )

            rt = Runtime(rsp, dic)
            ts.rt = rt

            for addr, br in breakpoints.items():
                if not br.exprs:
                    continue
                rt.br(addr, br, quiet = quiet)

            disp.enqueue(rt.co_run_target(kill = False))
            disp.enqueue(ts.co_main())
            disp.dispatch_all()

            qmp("cont")
            qmp("quit")
        finally:
            emu_p.wait()
            port_pool.free_port(qmp_port)
            port_pool.free_port(gdb_port)

        if ts.result != "PASSED":
            exit_code -= 1

    return exit_code


if __name__ == "__main__":
    exit(main() or 0)
