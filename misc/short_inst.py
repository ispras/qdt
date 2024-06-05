from common.pygen import (
    dumps,
)
from qemu.cpu.instruction import (
    Instruction,  # for exec
    Opcode,  # for exec
    Operand,
)
from qemu.cpu.short import (
    Short,
)
from source import (
    BlockParser,
)

from argparse import (
    ArgumentParser,
)
from copy import (
    deepcopy,
)
from re import (
    compile,
)
from traceback import (
    format_exc,
)

re_opspec = compile("(" + Short.t_ID + r")\s*=\s*([01]+)(\s+.*)?")


def check_dump(insn):
    code = dumps(insn)
    print(code)
    locals_ = {}
    exec(code, globals(), locals_)
    loaded_code = dumps(locals_["obj"])
    if code != loaded_code:
        print(loaded_code)
        raise AssertionError("dumps/loads-ed instruction differs")


def print_layout(insn):
    print(insn.bitsize)
    offset = 0
    for f in insn.fields:
        print("\t%2d %2d %s" % (
            offset,
            f.bitsize,
            f.name if isinstance(f, Operand) else f.val,
        ))
        offset += f.bitsize


def handle_insn(insn):
    print("\n\n")
    check_dump(insn)
    print_layout(insn)


def main():
    ap = ArgumentParser()
    arg = ap.add_argument

    arg("short_desc_file_name")
    arg("-r", "--read-bitsize",
        default = 32,
        type = int,
    )

    args = ap.parse_args()
    read_bitsize = args.read_bitsize

    with open(args.short_desc_file_name, "r") as f:
        short_desc = f.read()

    bp = BlockParser()
    top_block = bp.parse(short_desc)

    # analyze instructions

    for line in top_block:
        l = str(line)
        if not l:
            continue
        try:
            insn = Short.parse(l)
        except:
            # before debug call stack another exception
            msg = format_exc()
            try:
                Short.parse(l, debug = True)
            except:
                pass
            # after parser log printed
            print(msg)
            return 1

        insn.read_bitsize = read_bitsize
        insn.is_family = False
        line.insn = insn

        stack = [line.subblock]

        while stack:
            sb = stack.pop()

            if not sb:
                continue

            for sline in sb:
                m = re_opspec.match(str(sline))
                if not m:
                    continue

                op_name, op_val, __ = m.groups()
                op_val_len = len(op_val)
                parent_insn = sb.heading.insn
                parent_insn.is_family = True

                op_val = int(op_val, base = 2)

                insn = deepcopy(parent_insn)
                insn.is_family = False
                sline.insn = insn

                raw_fields = list(insn.raw_fields)

                for i, f in enumerate(raw_fields):
                    if not isinstance(f, Operand):
                        continue
                    if f.name != op_name:
                        continue

                    assert op_val_len <= f.bitsize
                    raw_fields[i] = Opcode(f.bitsize, val = op_val)
                    break
                else:
                    raise ValueError(
                        "No place for opcode '%s' defined" % op_name
                    )

                insn.raw_fields = tuple(raw_fields)

                stack.append(sline.subblock)

    # print instructions

    stack = [top_block]

    while stack:
        b = stack.pop()

        if not b:
            continue

        for l in b:
            stack.append(l.subblock)

            i = getattr(l, "insn", None)
            if i is None:
                continue
            if i.is_family:
                continue
            handle_insn(i)


if __name__ == "__main__":
    exit(main() or 0)
