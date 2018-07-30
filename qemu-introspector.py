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
from pyrsp.runtime import (
    Runtime
)
from itertools import (
    count
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


re_qemu_system_x = compile(".*qemu-system-.+$")


class QArgumentParser(ArgumentParser):

    def error(self, *args, **kw):
        stderr.write("Error in argument string. Ensure that `--` is passed"
            " before QEMU and its arguments.\n"
        )
        super(QArgumentParser, self).error(*args, **kw)


# Characters disalowed in node ID according to DOT language. That is not a full
# list though.
# https://www.graphviz.org/doc/info/lang.html
re_DOT_ID_disalowed = compile(r"[^a-zA-Z0-9_]")

class QOMTreeGetter(object):

    def __init__(self, runtime, dot_file_name = None):
        self.rt = runtime
        dia = runtime.dia
        object_c = dia.get_CU_by_name("object.c")

        # get address for specific line inside object.c (type_register_internal)
        dia.account_line_program_CU(object_c)
        line_map = dia.find_line_map("object.c")

        line_137 = line_map[137]
        line_138 = line_map[138]

        br_addr = line_137[0].state.address

        self.target = target = runtime.target

        br_addr_str = target.get_hex_str(br_addr)
        print("type_register_internal entry: 0x%s" % br_addr_str)

        target.set_br(br_addr_str, self.on_type_register_internal)

        # set finish breakpoint in main just after QOM module initialization
        main = dia["main"]
        dia.account_line_program_CU(main.die.cu)
        vl_c_line_map = dia.find_line_map("vl.c")
        main_addr = vl_c_line_map[3075][0].state.address
        main_addr_str = target.get_hex_str(main_addr)

        print("finish br in `main`: 0x%s" % main_addr_str)
        target.set_br(main_addr_str, self.on_main)

        if dot_file_name is None:
            dot_file = None
        else:
            dot_file = open(dot_file_name, "wb")
            dot_file.write("""\
digraph QOM {
    rankdir=LR;
    node [shape=polygon fontname=Momospace]
    edge [style=filled]
"""
            )
            self.name2node = {}
            self.nodes = {}

        self.dot_file = dot_file

        target.on_finish.append(self.finalize)

    def node(self, name):
        node_base = re_DOT_ID_disalowed.sub("_", name)
        nodes = self.nodes

        if node_base in nodes:
            counter = nodes[node_base]
            if counter is None:
                nodes[node_base] = counter = count(0)

            node = "%s__%d" % (node_base, next(counter))
        else:
            node = node_base
            nodes[node_base] = None

        self.name2node[name] = node
        return node

    def on_type_register_internal(self):
        rt = self.rt

        info = rt["info"]
        name = info["name"]
        parent = info["parent"]

        parent_s, name_s = parent.fetch_c_string(), name.fetch_c_string()

        if parent_s is None:
            parent_s = "NULL"

        print("%s -> %s" % (parent_s, name_s))

        dot = self.dot_file
        if dot is not None:
            n2n = self.name2node

            if parent_s in n2n:
                parent_n = n2n[parent_s]
            else:
                parent_n = self.node(parent_s)
                dot.write(b'\n\n    %s [label = "%s"]' % (parent_n, parent_s))

            if name_s in n2n:
                name_n = n2n[name_s]
            else:
                name_n = self.node(name_s)
                dot.write(b'\n\n    %s [label = "%s"]' % (name_n, name_s))

            dot.write(b"\n    %s -> %s" % (parent_n, name_n))

        rt.on_resume()

    def on_main(self):
        self.rt.target.interrupt()

    def finalize(self):
        if self.dot_file:
            self.dot_file.write(b"\n}\n")
            self.dot_file.close()


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
    dia = DWARFInfoAccelerator(di)

    object_c = dia.get_CU_by_name("object.c")

    # get address for specific line inside object.c (type_register_internal)
    dia.account_line_program_CU(object_c)
    line_map = dia.find_line_map("object.c")

    br_addr = line_map[136][0].state.address

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

    br_addr_str = qemu_debugger.get_hex_str(br_addr)
    print("addr 0x%s" % br_addr_str)

    br_cb = runtime_based_var_getting(rt)
    qemu_debugger.set_br(br_addr_str, br_cb)

    qemu_debugger.run()

    qemu_debugger.rsp.finish()
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
