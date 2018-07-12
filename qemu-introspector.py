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
from pyrsp.intervalmap import (
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

    dia = DWARFInfoAccelerator(elf.get_dwarf_info())

    object_c = dia.get_CU_by_name("object.c")

    # get info argument of type_register_internal function
    dia.account_subprograms(object_c)
    type_register_internal = dia.subprograms["type_register_internal"][0]
    info = type_register_internal.data["info"]

    # get address for specific line inside object.c (type_register_internal)
    dia.account_line_program_CU(object_c)
    line_map = dia.find_line_map("object.c")

    br_addr = line_map[136][0].state.address

    print("info loc: %s" % info.location)

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

    br_addr_str = qemu_debugger.get_hex_str(br_addr)
    print("addr 0x%s" % br_addr_str)

    def type_reg():
        print("type reg")

    qemu_debugger.set_br(br_addr_str, type_reg)

    qemu_debugger.run()

    qemu_proc.join()


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
