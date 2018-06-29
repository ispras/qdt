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

    cache_file = qemu_debug + ".qec"

    loaded = {
        "AddrDesc": AddrDesc,
        "QELFCache": QELFCache,
        "intervalmap" : intervalmap
    }

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

    qemu_debug_addr = "localhost:4321"

    qemu_proc = Process(
        target = system,
        # XXX: if there are spaces in arguments this code will not work.
        args = (" ".join(["gdbserver", qemu_debug_addr] + qemu_cmd_args),)
    )

    qemu_proc.start()

    qemu_debugger = AMD64(qemu_debug_addr,
        elffile = qemu_debug,
        verbose = True,
        host = True
    )

    qemu_debugger.run()

    qemu_proc.join()


if __name__ == "__main__":
    exit(main())
