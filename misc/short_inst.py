from qemu.cpu.instruction import (
    Operand,
)
from qemu.cpu.short import (
    Short,
)

from argparse import (
    ArgumentParser,
)
from traceback import (
    format_exc,
)


def main():
    ap = ArgumentParser()
    arg = ap.add_argument

    arg("short_desc_file_name")

    args = ap.parse_args()

    with open(args.short_desc_file_name, "r") as f:
        short_desc = f.read()

    short_lines = short_desc.splitlines(False)
    l = short_lines[1]

    try:
        res = Short.parse(l)
    except:
        # before debug call stack another exception
        msg = format_exc()
        res = None
        try:
            Short.parse(l, debug = True)
        except:
            pass
        # after parser log printed
        print(msg)
        return 1

    print(res)
    res.read_bitsize = 32
    print(res.bitsize)
    offset = 0
    for f in res.fields:
        print("\t%2d %2d %s" % (
            offset,
            f.bitsize,
            f.name if isinstance(f, Operand) else f.val,
        ))
        offset += f.bitsize

if __name__ == "__main__":
    exit(main() or 0)
