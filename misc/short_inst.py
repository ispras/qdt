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
from qemu.cpu.short_statement import (
    DefineFinder,
    ShortStatement,
    VersatileIdentifier,
)
from source import (
    BlockParser,
    Line,
)
from source.c_const import (
    CSTR,
)
from source.function.tree import (
    Comment,
)

from argparse import (
    ArgumentParser,
)
from collections import (
    defaultdict,
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

re_opspec = compile("(" + Short.t_ID + r")\s*:=\s*(\"[^\"]+\")(\s+.*)?")

# Specification operator (:=) can set instruction attributes.
instruction_attributes = dict(
    branch = bool,
    disas_format = str,
    # some attributes cannot be set using := operator
    # "comment",
    # "semantics,
    priority = int,
)


def check_dump(insn):
    code = dumps(insn)
    print(code)
    locals_ = {}
    exec(code, globals(), locals_)
    for loaded in locals_.values():
        if isinstance(loaded, Instruction):
            break
    else:
        raise AssertionError("code does not provide Instruction object")
    loaded_code = dumps(loaded)
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


class InstructionsList(list):

    def __init__(self, list_name = "instructions"):
        super(InstructionsList, self).__init__()
        self.list_name = list_name

    def __pygen_pass__(self, g):
        instructions = list(self)
        yield instructions, True
        g.write(self.list_name + " = ")
        g.pprint(instructions)


def analyze_instruction_block(heading):
    heading.insn = None

    l = str(heading)
    # remove comments from top block lines
    l = l.split("#")[0]

    if not l:
        return

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

    heading.insn = insn

    find_instruction_specifiers(heading)


def find_instruction_specifiers(heading):
    insn = heading.insn

    op_names = set(f.name for f in insn.raw_fields if isinstance(f, Operand))

    heading.specs = specs = defaultdict(list)

    stack = [heading]

    while stack:
        line = stack.pop()
        block = line.child

        if not block:
            continue

        for sline in block:
            m = re_opspec.match(str(sline))
            if not m:
                stack.append(sline)
                continue

            op_name, op_val, __ = m.groups()

            if op_name in op_names:
                specs[op_name].append(op_val)
                # Do not go deeper right now.
                # Some definitions can be for choisen instruction variants.
                # They will be handled later during recursive
                #     `iter_multiply_instruction_blocks` calls.
            else:
                stack.append(sline)


def find_attribute_definitions(heading):
    attrs = {}

    stack = [heading]

    while stack:
        line = stack.pop()
        block = line.child

        if not block:
            continue

        for sline in block:
            stack.append(sline)

            defines = DefineFinder(sline.stmnts).visit().defines

            for d in defines:
                name = d.name
                if isinstance(name, VersatileIdentifier):
                    def_name = name.name
                else:
                    raise SyntaxError(
                        "lvalue of `:=` must be an ID, not %r" % name
                    )

                value = d.value
                if isinstance(value, CSTR):
                    op_val = str(value)
                else:
                    raise SyntaxError(
                        'rvalue of `:=` must be a "str", not %r' % value
                    )

                if def_name in instruction_attributes:
                    assert def_name not in attrs
                    attrs[def_name] = op_val

    heading.attrs = attrs


def specified_line(orig_line, op_name, op_val):
    if orig_line.child:
        # TODO: it might be not so simple
        line = Line(orig_line)

        line.child = type(orig_line.child)(
            iter_block_lines_specified(
                 op_name, op_val, orig_line.child
            )
        )
    else:
        line = orig_line
    return line


def iter_block_lines_specified(op_name, op_val, block):
    for line in block:
        m = re_opspec.match(str(line))
        if not m:
            yield specified_line(line, op_name, op_val)
            continue

        l_op_name, l_op_val, comment = m.groups()
        if l_op_name == op_name:
            if l_op_val == op_val:

                # TODO: it might be not so simple
                if comment:
                    yield Line(comment)
                else:
                    yield Line()

                if line.child:
                    for sline in iter_block_lines_specified(
                        op_name, op_val, line.child
                    ):
                        yield sline

        else:
            yield specified_line(line, op_name, op_val)


def iter_multiply_instruction_blocks(heading):
    specs = heading.specs
    if not specs:
        yield heading
        return

    op_name = sorted(specs)[0]
    op_vals = specs.pop(op_name)

    # don't deepcopy of parent
    heading.parent = None

    for op_val in op_vals:
        specified = deepcopy(heading)

        block = specified.child

        # TODO: it might be not so simple
        block[:] = iter_block_lines_specified(op_name, op_val, block)

        insn = specified.insn

        specify_instruction_operand(insn, op_name, op_val)

        # - Possibly, there are operand specifications those are actual for
        #   this specified instruction (variant) only.
        # - Substitution might add more operands that could be specified.
        #   So, more `name := value` pairs could be distinguished as
        #   specifications.
        find_instruction_specifiers(specified)

        for subspec in iter_multiply_instruction_blocks(specified):
            yield subspec


def specify_instruction_operand(insn, op_name, op_val):
    # find place to substitute
    for field_i, f in enumerate(insn.raw_fields):
        if not isinstance(f, Operand):
            continue
        if f.name == op_name:
            break
    else:
        raise ValueError(
            "No place for opcode '%s' defined" % op_name
        )

    l = eval(op_val)
    try:
        sub_insn = Short.parse(l)
    except:
        # before debug call stack another exception
        msg = format_exc()
        try:
            Short.parse(l, debug = True)
        except:
            pass
        # after parser log printed
        print(msg)
        raise

    if isinstance(sub_insn, Instruction):
        insn.mnemonic = sub_insn.mnemonic
        sub_raw_fields = sub_insn.raw_fields
    else:
        sub_raw_fields = sub_insn

    sub_raw_fields_size = sum(f.bitsize for f in sub_raw_fields)
    assert sub_raw_fields_size == f.bitsize

    raw_fields = list(insn.raw_fields)
    raw_fields[field_i:(field_i + 1)] = sub_raw_fields
    insn.raw_fields = tuple(raw_fields)


def set_attributes(heading):
    find_attribute_definitions(heading)

    insn = heading.insn
    block = heading.child

    for attr, val_str in heading.attrs.items():
        val = eval(val_str)

        setattr(insn, attr, instruction_attributes[attr](val))

        block[:] = iter_block_lines_specified(attr, val_str, block)


def fill_comment(heading):
    comment_lines = []

    stack = [(0, heading)]

    while stack:
        indent, line = stack.pop()

        line_str = str(line)
        if line_str:
            comment_lines.append("    " * indent + line_str)
        else:
            comment_lines.append("")

        block = line.child

        if not block:
            continue

        for sline in reversed(block):
            stack.append((indent + 1, sline))

    heading.insn.comment = "\n".join(comment_lines)


def parse_lines(heading):
    block = heading.child

    if block is None:
        return

    for line in block:
        # strip comment
        parts = str(line).split("#", 1)
        code = parts[0].strip()
        if len(parts) > 1:
            comment = parts[1].strip()
            stmnts = [Comment(comment)]
        else:
            stmnts = []

        if code:
            try:
                stmnt = ShortStatement.parse(code)
            except:
                # before debug call stack another exception
                msg = format_exc()
                print("code: " + code)
                try:
                    ShortStatement.parse(code, debug = True)
                except:
                    pass
                # after parser log printed
                print(msg)
                raise
            else:
                stmnts.append(stmnt)

        line.stmnts = stmnts

        parse_lines(line)


def main():
    ap = ArgumentParser(
        description = """\
Converts short form instructions definitions to script defines them.
"""     ,
    )
    arg = ap.add_argument

    arg("short_desc_file_name")
    arg("-r", "--read-bitsize",
        default = 32,
        type = int,
    )
    arg("-o", "--output-file-name")
    arg("-n", "--list-name",
        default = "instructions",
        type = str,
        help = "name of list of instructions",
    )

    args = ap.parse_args()
    read_bitsize = args.read_bitsize
    output_file_name = args.output_file_name

    with open(args.short_desc_file_name, "r") as f:
        short_desc = f.read()

    bp = BlockParser()
    top_block = bp.parse(short_desc)

    # analyze instructions

    insn_lines = []

    for top_line in top_block:
        analyze_instruction_block(top_line)

        insn = top_line.insn
        if insn is None:
            continue

        insn.read_bitsize = read_bitsize

        insn_lines.extend(iter_multiply_instruction_blocks(top_line))

    # handle instructions

    insts = InstructionsList(
        list_name = args.list_name,
    )

    for heading in insn_lines:
        parse_lines(heading)
        set_attributes(heading)
        fill_comment(heading)

        i = heading.insn

        handle_insn(i)
        insts.append(i)

    if output_file_name:
        insts_text = dumps(insts)
        with open(output_file_name, "w") as f:
            f.write("# this file is generated by " + ap.prog + "\n")
            f.write("from qemu import *\n")
            f.write("\n")
            f.write(insts_text + "\n")


if __name__ == "__main__":
    exit(main() or 0)
