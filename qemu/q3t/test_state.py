__all__ = [
    "is_q3t_name"
      , "only_q3t_items"
  , "build_addr2srclines_map"
  , "print_addr2srclines_map"
  , "Q3TTestState"
]
from common import (
    FileLinesCache,
    intervalmap,
    iter_trie_items,
)
from debug import (
    DWARFInfoCache,
    InMemoryELFFile,
    rpath2path,
    Runtime,
    SymTab,
)
from .helpers import *  # populate `globals()`

try:
    import builtins
except ImportError:
    # Py2 ?
    import __builtin__ as builtins
from collections import (
    OrderedDict,
)
from functools import (
    wraps,
)
from os.path import (
    abspath,
    join,
    split,
)
from time import (
    time,
)
from traceback import (
    format_exc,
)


AUTO_EXPRS = tuple(dict(
    q3t_quit = "q3t_quit()",
).items())


def is_q3t_name(n):
    return n.startswith("q3t")

def only_q3t_items(ii):
    for i in ii:
        if is_q3t_name(i[0]):
            yield i


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
        self.aliases = [name]

    def __call__(self):
        ts = self.ts
        ts.t_last_br = time()
        verbose = ts.verbose
        if verbose:
            print("hit: " + ", ".join(self.aliases))
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
                print("\tres: %r" % (res,))

            ts.t_last_br = time()


def gen_callable_verbose_wrapper(n, v):
    @wraps(v)
    def wrapper(*a, **kw):
        ret = v(*a, **kw)
        print("\t%s(...): " % (n,) + format_val(ret))
        return ret
    return wrapper


def build_addr2srclines_map(srcmap):
    a2sl = intervalmap()
    for rpath, lmap in iter_trie_items(srcmap):
        for (begin_line, end_line), entries in lmap.items():
            for entry in entries:
                state = entry.state
                if state.end_sequence:
                    continue
                addr = state.address
                _, end_addr = a2sl.interval(addr)
                a2sl[addr:end_addr] = (rpath, begin_line, end_line)
    return a2sl


def print_addr2srclines_map(amap):
    entries = []
    max_addr_len = 0
    for (s, e), (rpath, begin_line, end_line) in amap.items():
        s = "%x" % s
        if e is None:
            e = ""
        else:
            e = "%x" % e
        max_addr_len = max(len(s), len(e), max_addr_len)
        entries.append((
            s, e, str(begin_line), str(end_line), rpath2path(rpath)
        ))
    fmt = ("%%%ds" % max_addr_len).__mod__
    prev_path = None
    for ba, ea, bl, el, path in entries:
        if prev_path != path:
            prev_path = path
            sfx = " " + path
        else:
            sfx = ""
        print("\t" + fmt(ba) + ":" + fmt(ea) + " < " + bl + ":" + el + sfx)


file_lines_cache = FileLinesCache()


class Q3TTestState(object):

    rt = None
    qmp = None

    def __init__(self,
        timeout = 5.0,
        verbose = False,
        failures = 1,
        bp_infix = "q3t",
        expr_prefix = ">>>",
    ):
        self.working = True
        self.verbose = verbose
        self.max_failures = failures
        self.bp_infix = bp_infix
        self.expr_prefix = expr_prefix
        self.failures = []
        self.timed_out = False
        self.t_last_br = None
        self.timeout = timeout
        self.namespace = {}
        # output must be deterministic
        self.breakpoints = OrderedDict()

    def update_namespace(self, data, wrap = True):
        ns = self.namespace
        if wrap and self.verbose:
            func_t = type(only_q3t_items)
            method_t = type(self.q3t_quit)
            builtin_callable_t = type(abs)
            callable_tt = (func_t, method_t, builtin_callable_t)

            for n, v in tuple(dict(data).items()):
                if isinstance(v, callable_tt):
                    v = gen_callable_verbose_wrapper(n, v)
                ns[n] = v
        else:
            ns.update(data)

    def populate_namespace(self):
        self.update_namespace(
            (n, getattr(self, n)) for n in dir(self) if is_q3t_name(n)
        )

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

    def q3t_memeq(self, a, b, size):
        return self.q3t_ld(a, size) == self.q3t_ld(b, size)

    def fail(self, locs):
        # locs (`ExpressionLocals`) has reference to `Q3TBreakpoint`
        self.failures.append(locs)
        if len(self.failures) == self.max_failures:
            self.working = False
            self.rt.exit()

    def parse_elf(self, bin_file_path):
        elf = InMemoryELFFile(bin_file_path)
        di = elf.get_dwarf_info()
        symtab_sect = elf.get_section_by_name(".symtab")
        symtab = SymTab(symtab_sect)
        sym2addr = symtab.address_map
        self.sym2addr = sym2addr
        breakpoints = self.breakpoints
        bp_infix = self.bp_infix
        for name, addr in sym2addr.items():
            if bp_infix not in name:
                continue
            bp = breakpoints.get(addr)
            if bp is None:
                bp = Q3TBreakpoint(self, name, addr)
                breakpoints[addr] = bp
            else:
                bp.aliases.append(name)

        dic = DWARFInfoCache(di,
            symtab = symtab_sect,
        )
        self.dic = dic

        # account all line programms
        for cu in dic.iter_CUs():
            dic.account_line_program_CU(cu)

        a2sl = build_addr2srclines_map(dic.srcmap)
        self.a2sl = a2sl

        bin_file_dir, bin_file_name = split(bin_file_path)
        self.bin_file_dir = bin_file_dir
        self.bin_file_name = bin_file_name

        prefix = self.expr_prefix

        for addr, br in breakpoints.items():
            aliases = br.aliases
            append_expr = br.exprs.append

            rpath, begin_line, end_line = a2sl[addr]
            src_path = abspath(join(bin_file_dir, rpath2path(rpath)))
            br.src_path = src_path
            br.begin_line = begin_line
            br.end_line = end_line

            for line in file_lines_cache[src_path][begin_line:end_line]:
                i = line.find(prefix)
                if i < 0:
                    continue
                expr = line[i+3:].strip()
                append_expr(expr)

            br.first_auto_expr = len(br.exprs)
            for infix, expr in AUTO_EXPRS:
                for name in aliases:
                    if infix in name:
                        append_expr(expr)

    def co_main(self, qmp, rsp, quiet = True):
        self.update_namespace(self.sym2addr)
        yield True
        self.update_namespace(global_q3t)
        yield True
        self.update_namespace(builtins.__dict__.items())
        yield True
        self.populate_namespace()
        yield True

        self.qmp = qmp

        rt = Runtime(rsp, self.dic)
        self.rt = rt

        yield True

        for addr, br in self.breakpoints.items():
            if br.exprs:
                yield True
                rt.br(addr, br, quiet = quiet)

        if self.t_last_br is None:
            self.t_last_br = time()

        rst_t = rt.start_rsp_thread(kill = False)

        yield True

        while self.working and rst_t.is_alive():
            t = time()
            dt = t - self.t_last_br
            if dt > self.timeout:
                self.rt.exit()
                self.qmp("stop")
                self.timed_out = True

            if self.result != "PASSED":
                break

            yield False

        while rst_t.is_alive():
            yield False

        qmp("cont")
        qmp("quit")

        print("result: " + self.result)

    def iter_brs_info_lines(self):
        breakpoints = self.breakpoints
        if breakpoints:
            yield "breakpoint(s) found: " + str(len(breakpoints))
        else:
            yield "No breakpoint(s) found"
            return

        for addr, br in breakpoints.items():
            print("%s 0x%X at %r %u:%u" % (
                ", ".join(br.aliases),
                addr,
                br.src_path,
                br.begin_line,
                br.end_line,
            ))

            exprs = br.exprs
            if exprs:
                first_auto_expr = br.first_auto_expr

                for expr in exprs[:first_auto_expr]:
                    print("\t%r" % expr)
                for expr in exprs[first_auto_expr:]:
                    print("\t%r # auto" % expr)
            else:
                print("\tno expressions")

    @property
    def brs_info(self):
        return "\n".join(self.iter_brs_info_lines())

    def print_brs_info(self):
        print(self.brs_info)


global_q3t = dict(only_q3t_items(globals().items()))
