from qemu.introspection import (
    q_event_dict,
    q_event_list
)
from argparse import (
    ArgumentTypeError,
    ArgumentParser,
    ArgumentError
)
from re import (
    compile
)
from collections import (
    defaultdict,
    deque
)
from multiprocessing import (
    Process
)
from os import (
    system
)
from os.path import (
    isfile,
    split,
    join
)
from sys import (
    stderr,
    path as python_path
)
# Add ours pyelftools to PYTHON_PATH before importing of pyrsp to substitute
# system pyelftools imported by pyrsp
for mod in ("pyrsp", "pyelftools"):
    path = join(split(__file__)[0], mod)
    if path not in python_path:
        python_path.insert(0, path)

from pyrsp.targets import (
    AMD64
)
from pyrsp.elf import (
    InMemoryELFFile,
    DWARFInfoAccelerator,
    ELF,
    AddrDesc
)
from elftools.common.intervalmap import (
    intervalmap
)
from hashlib import (
    sha1
)
from common import (
    sort_topologically,
    PyGenerator,
    execfile
)
from traceback import (
    print_exc
)
from pyrsp.utils import (
    switch_endian,
    decode_data
)
from pyrsp.gdb import (
    Value,
    Type
)
from pyrsp.type import (
    TYPE_CODE_PTR
)
from pyrsp.runtime import (
    Runtime
)
from itertools import (
    count
)
from inspect import (
    getmembers,
    ismethod
)
from graphviz import (
    Digraph
)


def checksum(stream, block_size):
    "Given a stream computes SHA1 hash by reading block_size per block."

    buf = stream.read(block_size)
    hasher = sha1()
    while len(buf) > 0:
        hasher.update(buf)
        buf = stream.read(block_size)


def elf_stream_checksum(stream, block_size = 65536):
    return checksum(stream, block_size)


def elf_checksum(file_name):
    with open(file_name, "rb") as s: # Stream
        return elf_stream_checksum(s)


class QELFCache(ELF):
    """
Extended version of ELF file cache.

Extra features:
- SHA1 based modification detection code, `mdc` field.
- serialization to Python script by `PyGeneratior`

    """

    # names of fields to serialize
    SAVED = (
        # QELFCache fields
        "mdc",
        # backing class fields
        "entry", "rel", "workarea", "symbols", "addresses", "file_map",
        "src_map", "addr_map", "routines", "vars",
    )

    def __init__(self, name, **kw):
        mdc = kw.get("mdc", None)
        file_mdc = elf_checksum(name)

        if mdc is None:
            # build the cache
            super(QELFCache, self).__init__(name)
            self.mdc = file_mdc
        else:
            # check the cache
            if file_mdc != mdc:
                raise ValueError("File SHA1 %r was changed. Expected: %r" % (
                    file_mdc, mdc
                ))

            absent = deque()

            for field in self.SAVED:
                try:
                    val = kw[field]
                except KeyError:
                    absent.append(val)
                setattr(self, field, val)

            if absent:
                raise TypeError("Some data are absent: " + ", ".join(absent))

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field("")
        gen.pprint(self.name)
        for field in self.SAVED:
            gen.gen_field(field + " = ")
            gen.pprint(getattr(self, field))
        gen.gen_end()

    def __dfs_children__(self):
        return [self.addr_map] + list(self.file_map.values())

    def __var_base__(self):
        return "qec"


re_breakpoint_pos = compile("^[^:]*:[1-9][0-9]*$")


def is_breakpoint_cb(object):
    if not ismethod(object):
        return False
    if not object.__name__.startswith("on_"):
        return False
    doc = object.__doc__
    return doc and re_breakpoint_pos.match(doc.splitlines()[0])


class Watcher(object):

    def __init__(self, dia, verbose = True):
        self.dia = dia
        self.verbose = verbose

        # inspect methods getting those who is a breakpoint handler
        self.breakpoints = brs = []
        for name, cb in getmembers(type(self), predicate = is_breakpoint_cb):
            file_name, line_str = cb.__doc__.splitlines()[0].split(":")
            line_map = dia.find_line_map(file_name)
            line_descs = line_map[int(line_str)]
            addr = line_descs[0].state.address
            brs.append((addr, getattr(self, name)))

    def init_runtime(self, rt):
        v = self.verbose
        quiet = not v

        self.rt = rt
        target = rt.target

        for addr, cb in self.breakpoints:
            addr_str = target.get_hex_str(addr)

            if v:
                print("br 0x" + addr_str + ", handler = " + cb.__name__)

            target.set_br(addr_str, cb, quiet = quiet)

    def remove_breakpoints(self):
        "Removes breakpoints assigned by `init_runtime`."

        target = self.rt.target
        quiet = not self.verbose

        for addr, _ in self.breakpoints:
            addr_str = target.get_hex_str(addr)
            target.del_br(addr_str, quiet = quiet)


re_qemu_system_x = compile(".*qemu-system-.+$")


class QArgumentParser(ArgumentParser):

    def error(self, *args, **kw):
        stderr.write("Error in argument string. Ensure that `--` is passed"
            " before QEMU and its arguments.\n"
        )
        super(QArgumentParser, self).error(*args, **kw)


class RQOMTree(object):
    """ QEmu object model tree descriptor at runtime
    """

    def __init__(self):
        self.name2type = {}
        self.addr2type = {}

        # Types are found randomly (i.e. not in parent-first order).
        self.unknown_parents = defaultdict(list)

    def account(self, impl, name = None, parent = None):
        "Add a type"
        if impl.type.code == TYPE_CODE_PTR:
            # Pointer `impl` is definetly a value on the stack. It cannot be
            # used as a global. Same time `TypeImpl` is on the heap. Hence, it
            # can. I.e. a dereferenced `Value` should be used.
            impl = impl.dereference()
        if not impl.is_global:
            impl = impl.to_global()

        info_addr = impl.address

        t = RQOMType(self, impl, name = name, parent = parent)

        name = t.name
        parent = t.parent

        self.addr2type[info_addr] = t
        self.name2type[name] = t

        unk_p = self.unknown_parents

        n2t = self.name2type
        if parent in n2t:
            n2t[parent].children.append(t)
        else:
            unk_p[parent].append(t)

        if name in unk_p:
            t.children.extend(unk_p.pop(name))

        return t

    def __getitem__(self, addr_or_name):
        if isinstance(addr_or_name, str):
            return self.name2type[addr_or_name]
        else:
            return self.addr2type[addr_or_name]


class RQOMType(object):
    """ QEmu object model type descriptor at runtime
    """

    def __init__(self, tree, impl, name = None, parent = None):
        """
        :param impl:
            global runtime `Value` which is pointer to the `TypeImpl`

        :param name:
            `str`ing read form impl

        :param parent:
            `str`ing too
        """
        self.tree = tree
        self.impl = impl
        if name is None:
            name = impl["name"].fetch_c_string()
        if parent is None:
            parent = impl["parent"].fetch_c_string()
            # Parent may be None
        self.name, self.parent = name, parent

        self.children = []

    def __dfs_children__(self):
        return self.children

    def iter_ancestors(self):
        n2t = self.tree.name2type
        cur = self.parent

        while cur is not None:
            t = n2t[cur]
            yield t
            cur = t.parent

    def implements(self, name):
        if name == self.name:
            return True
        t = self.tree.name2type[name]

        for a in self.iter_ancestors():
            if a is t:
                return True
        return False


# Characters disalowed in node ID according to DOT language. That is not a full
# list though.
# https://www.graphviz.org/doc/info/lang.html
re_DOT_ID_disalowed = compile(r"[^a-zA-Z0-9_]")


def gv_node(label):
    return re_DOT_ID_disalowed.sub("_", label)


class QOMTreeGetter(Watcher):

    def __init__(self, dia, interrupt = True, verbose = True):
        """
        :param interrupt:
            Stop QEmu and exit `RemoteTarget.run`.
        """
        super(QOMTreeGetter, self).__init__(dia, verbose = verbose)

        self.tree = RQOMTree()
        self.interrupt = interrupt

    def on_type_register_internal(self):
        "object.c:139" # type_register_internal

        # Pointer `ti` is a value on the stack. It cannot be used as a global.
        # While `TypeImpl` is on the heap. Hence, it can. I.e. a dereferenced
        # `Value` should be used.
        t = self.tree.account(self.rt["ti"].dereference())

        if self.verbose:
            print("%s -> %s" % (t.parent, t.name))

    def on_main(self):
        "vl.c:3075" # main, just after QOM module initialization

        if self.interrupt:
            self.rt.target.interrupt()

    def to_file(self, dot_file_name):
        graph = Digraph(
            name = "QOM",
            graph_attr = dict(
                rankdir = "LR"
            ),
            node_attr = dict(
                shape = "polygon",
                fontname = "Momospace"
            ),
            edge_attr = dict(
                style = "filled"
            ),
        )

        for t in sort_topologically(
            v for v in self.tree.name2type.values() if v.parent is None
        ):
            n = gv_node(t.name)
            graph.node(n, label = t.name + "\\n0x%x" % t.impl.address)
            if t.parent:
                graph.edge(gv_node(t.parent), n)

        with open(dot_file_name, "wb") as f:
            f.write(graph.source)


class QInstance(object):
    """ Descriptor for QOM object at runtime.
    """

    def __init__(self, obj, type):
        self.obj = obj
        self.type = type
        self.related = []


class MachineWatcher(Watcher):
    """ Watches for QOM API calls to reconstruct machine model and monitor its
    state at runtime.
    """

    def __init__(self, dia, qom_tree, verbose = True):
        super(MachineWatcher, self).__init__(dia, verbose = verbose)
        self.tree = qom_tree
        # addr -> QInstance mapping
        self.instances = {}

    def on_obj_init_start(self):
        "object.c:384" # object_initialize_with_type

        _type = self.rt["type"]
        name_ptr = _type["name"]
        name = name_ptr.fetch_c_string()

        print("creating instance of " + str(name))

    def on_obj_init_end(self):
        "object.c:386" # object_initialize_with_type
        rt = self.rt


def main():
    ap = QArgumentParser(
        description = "QEMU runtime introspection tool"
    )
    ap.add_argument("qarg",
        nargs = "+",
        help = "QEMU executable and arguments to it. Prefix them with `--`."
    )
    args = ap.parse_args()

    # executable
    qemu_cmd_args = args.qarg

    # debug info
    qemu_debug = qemu_cmd_args[0]

    loaded = {
        "AddrDesc": AddrDesc,
        "QELFCache": QELFCache,
        "intervalmap" : intervalmap
    }

    elf = InMemoryELFFile(qemu_debug)
    if not elf.has_dwarf_info():
        stderr("%s does not have DWARF info. Provide a debug QEMU build\n" % (
            qemu_debug
        ))
        return -1

    di = elf.get_dwarf_info()

    if di.pubtypes is None:
        print("%s does not contain .debug_pubtypes section. Provide"
            " -gpubnames flag to the compiller" % qemu_debug
        )

    dia = DWARFInfoAccelerator(di,
        symtab = elf.get_section_by_name(b".symtab")
    )

    qomtg = QOMTreeGetter(dia)
    mw = MachineWatcher(dia, qomtg.tree)

    qemu_debug_addr = "localhost:4321"

    qemu_proc = Process(
        target = system,
        # XXX: if there are spaces in arguments this code will not work.
        args = (" ".join(["gdbserver", qemu_debug_addr] + qemu_cmd_args),)
    )

    qemu_proc.start()

    qemu_debugger = AMD64(qemu_debug_addr,
        verbose = True,
        host = True
    )

    rt = Runtime(qemu_debugger, dia)

    mw.init_runtime(rt)
    qomtg.init_runtime(rt)

    qemu_debugger.run()

    qemu_debugger.rsp.finish()
    # XXX: on_finish method is not called by RemoteTarget
    qomtg.to_file("qom-by-q.i.dot")

    qemu_proc.join()


def runtime_based_var_getting(rt):
    target = rt.target

    def type_reg(resumes = [1]):
        print("type reg")
        info = rt["info"]
        name = info["name"]
        parent = info["parent"]

        p_name = parent.fetch(target.address_size)
        print("parent name at 0x%0*x" % (target.tetradsize, p_name))

        print("%s -> %s" % (parent.fetch_c_string(), name.fetch_c_string()))

        rt.on_resume()

        if resumes[0] == 0:
            rt.target.interrupt()
        else:
            resumes[0] -= 1

    return type_reg


def explicit_var_getting(rt, object_c):
    dia = rt.dia
    target = rt.target
    # get info argument of type_register_internal function
    dia.account_subprograms(object_c)
    type_register_internal = dia.subprograms["type_register_internal"][0]
    info = type_register_internal.data["info"]

    print("info loc: %s" % info.location)

    def type_reg_fields():
        print("type reg")
        info_loc = info.location.eval(rt)
        info_loc_str = "%0*x" % (target.tetradsize, info_loc)
        print("info at 0x%s" % info_loc_str)
        info_val = switch_endian(
            decode_data(
                target.get_mem(info_loc_str, 8)
            )
        )
        print("info = 0x%s" % info_val)
        pt = Type(dia, info.type_DIE)
        t = pt.target()
        print("info type: %s %s" % (" ".join(t.modifiers), t.name))
        # t is `typedef`, get the structure
        st = t.target()

        for f in st.fields():
            print("%s %s; // %s" % (f.type.name, f.name, f.location))

    def type_reg_name():
        v = Value(info, rt)
        name = v["name"]
        parent = v["parent"]

        p_name = parent.fetch(target.address_size)
        print("parent name at 0x%0*x" % (target.tetradsize, p_name))

        print("%s -> %s" % (parent.fetch_c_string(), name.fetch_c_string()))

    def type_reg():
        type_reg_name()
        type_reg_fields()

        rt.on_resume()

    return type_reg


def test_call_frame(type_register_internal, br_addr):
    frame = type_register_internal.frame_base

    print("frame base: %s" % frame)

    fde = dia.fde(br_addr)
    print("fde = %s" % fde)

    table_desc = fde.get_decoded()
    table = table_desc.table

    for row in table:
        print(row)

    call_frame_row = dia.cfr(br_addr)
    print("call frame: %s" % call_frame_row)
    cfa = dia.cfa(br_addr)
    print("CFA: %s" % cfa)


def test_subprograms(dia):
    cpu_exec = dia.get_CU_by_name("cpu-exec.c")

    # For testing:
    # pthread_atfork.c has subprogram data referencing location lists
    # ioport.c contains inlined subprogram, without ranges

    for cu in [cpu_exec]: # dia.iter_CUs():
        print(cu.get_top_DIE().attributes["DW_AT_name"].value)
        sps = dia.account_subprograms(cu)
        for sp in sps:
            print("%s(%s) -> %r" % (
                sp.name,
                ", ".join(varname for (varname, var) in sp.data.items()
                          if var.is_argument
                ),
                sp.ranges
            ))

            for varname, var in sp.data.items():
                print("    %s = %s" % (varname, var.location))


def test_line_program_sizes(dia):
    for cu in dia.iter_CUs():
        name = cu.get_top_DIE().attributes["DW_AT_name"].value
        print("Getting line program for %s" % name)
        li = dia.di.line_program_for_CU(cu)
        entries = li.get_entries()
        print("Prog size: %u" % len(entries))


def test_line_program(dia):
    cpu_exec = dia.get_CU_by_name("cpu-exec.c")

    lp = dia.di.line_program_for_CU(cpu_exec)
    entrs = lp.get_entries()

    print("%s line program (%u)" % (
        cpu_exec.get_top_DIE().attributes["DW_AT_name"].value,
        len(entrs)
    ))
    # print("\n".join(repr(e.state) for e in entrs))

    dia.account_line_program(lp)
    lmap = dia.find_line_map("cpu-exec.c")

    for (l, r), entries in lmap.items():
        s = entries[0].state
        print("[%6i;%6i]: %s 0x%x" % (
            1 if l is None else l,
            r - 1,
            "S" if s.is_stmt else " ",
            s.address
        ))


def test_CU_lookup(dia):
    dia.get_CU_by_name("tcg.c")
    print("found tcg.c")
    dia.get_CU_by_name(join("ui", "console.c"))
    print("found ui/vl.c")
    dia.get_CU_by_name(join("ui", "console.c"))
    print("found ui/vl.c again")
    dia.get_CU_by_name("console.c")
    print("found console.c")
    try:
        dia.get_CU_by_name("virtio-blk.c")
    except:
        dia.get_CU_by_name(join("block", "virtio-blk.c"))
        print("found block/virtio-blk.c")
    else:
        print("short suffix exception is expected")
    try:
        dia.get_CU_by_name("apic.c")
    except:
        dia.get_CU_by_name(join("kvm", "apic.c"))
        print("found kvm/apic.c")
    else:
        print("short suffix exception is expected")


def test_cache(qemu_debug):
    cache_file = qemu_debug + ".qec"

    if isfile(cache_file):
        print("Trying to load cache from %s" % cache_file)
        try:
            execfile(cache_file, globals = loaded)
        except:
            stderr.write("Cache file execution error:\n")
            print_exc()

        cache = loaded.get("qec", None)

        print("Cache was %sloaded." % ("NOT " if cache is None else ""))
    else:
        cache = None

    if cache is None:
        print("Building cache of %s" % qemu_debug)
        cache = QELFCache(qemu_debug)

        print("Saving cache to %s" % cache_file)
        with open(cache_file, "wb") as f:
            PyGenerator().serialize(f, cache)


if __name__ == "__main__":
    exit(main())
