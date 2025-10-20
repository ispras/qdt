__all__ = [
    "compute_instruction_tree_stats"
  , "print_instruction_tree"
  , "print_instruction_tree2"
  , "format_instruction"
  , "format_instructions"
  , "print_instructions"
  , "check_unreachable_instructions"
]

from common import (
    byN,
)

from collections import (
    namedtuple,
)


TreeStats = namedtuple(
    "TreeStats",
    "unreachable leaves min_depth aver_depth max_depth"
)


def traverse_tree(node, depths, used_instructions, depth = 0):
    if node.instruction is not None:
        used_instructions.append(node.instruction)
        depths.append(depth)
    else:
        for subtree in node.subtree.values():
            traverse_tree(subtree, depths, used_instructions, depth + 1)


def compute_instruction_tree_stats(node, instructions):
    depths = []
    used_instructions = []
    traverse_tree(node, depths, used_instructions)
    return TreeStats(
        unreachable = len(set(instructions) - set(used_instructions)),
        leaves = len(used_instructions),
        min_depth = min(depths),
        aver_depth = sum(depths) / float(len(depths)),
        max_depth = max(depths)
    )


def format_opcodes(opcodes, bitsize):
    return ", ".join(
        " ... ".join(
            "{1:0{0}b}".format(bitsize, subopcode) for subopcode in opcode
        ) for opcode in opcodes
    )

def print_instruction_tree(node, offset = ""):
    if node.instruction is not None:
        print("{0}{1}".format(offset, node.instruction.name))
    else:
        print("{0}[{1} {2}]:".format(offset, *node.interval))
        bitsize = node.interval[1]
        for opcodes, subtree in node.subtree.items():
            if opcodes is None:
                print("{0}default ({1}):".format(
                    offset,
                    format_opcodes(node.default_opcodes, bitsize)
                ))
            else:
                print("{0}{1}:".format(
                    offset,
                    format_opcodes(opcodes, bitsize)
                ))
            print_instruction_tree(subtree, offset + "    ")


def format_instruction(i, max_bitsize = None):
    if max_bitsize is None:
        max_bitsize = i.bitsize
    return "{1:<{0}} (priority {2}) mnemonic: {3}; comment: {4}".format(
        max_bitsize,
        i.opcode_bits_string,
        i.priority,
        i.mnemonic,
        i.comment
    )

def format_instructions(instructions, indent = "", max_bitsize = None):
    if max_bitsize is None:
        max_bitsize = max(i.bitsize for i in instructions)
    return "\n".join(
        indent + format_instruction(i, max_bitsize) for i in instructions
    )


def print_instructions(instructions, indent = "", max_bitsize = None):
    print(
        format_instructions(
            instructions,
            indent = indent,
            max_bitsize = max_bitsize
        )
    )


def check_unreachable_instructions(node, instructions):
    depths = []
    used_instructions = []
    traverse_tree(node, depths, used_instructions)
    unreachable_instructions = list(sorted(
        set(instructions) - set(used_instructions)
    ))
    if unreachable_instructions:
        print("WARNING: some instructions unreachable (check instructions"
            " encoding or priority):"
        )
        print_instructions(unreachable_instructions, indent = "    ")


def print_instruction_tree2(tree, offset = "\t"):
    _print_instruction_tree2(tree, dict(), 0, 0, offset)


def _print_instruction_tree2(node, checked_bits, indent, max_bit_n, offset):
    pfx = offset * indent

    ins = node.instruction
    if ins is None:
        next_checked_bits_base = dict(checked_bits)
        bitoffset, bitsize = node.interval
        for n in range(bitoffset, bitoffset + bitsize):
            next_checked_bits_base[n] = "."
        max_bit_n = max(max_bit_n, n)

        checkline = []
        for i in range(max_bit_n + 1):
            if i and not (i & 0x7):
                checkline.append(" ")
            if i in checked_bits:
                checkline.append(checked_bits[i])
            elif i < bitoffset or bitoffset + bitsize <= i:
                checkline.append("?")
            else:
                checkline.append("x")

        print(pfx + "".join(checkline))

        code_fmt = "{0:0%db}" % bitsize
        code_pfx = " " * bitoffset

        for opcodes, sub_node in node.subtree.items():
            if opcodes is None:
                code_lines = [pfx + code_pfx + "*" * bitsize]
            else:
                for opcode in opcodes:
                    if len(opcode) == 1:
                        code_str = code_fmt.format(opcode[0])
                        code_lines = [pfx + code_pfx + code_str]
                    else:  # xxx...yyy
                        code_lines = [
                            pfx + code_pfx + code_fmt.format(opcode[0]),
                            pfx + code_pfx + "." * bitsize,
                            pfx + code_pfx+ code_fmt.format(opcode[1]),
                        ]
            for line in code_lines:
                line = " ".join(
                    "".join(byte) for byte in byN(8, line, "")
                )
                print(line)
            if opcodes and len(opcodes) == 1 and len(opcodes[0]) == 1:
                next_checked_bits = dict(next_checked_bits_base)
                for i, b in enumerate(code_str, bitoffset):
                    next_checked_bits[i] = b
            else:
                next_checked_bits = next_checked_bits_base
            _print_instruction_tree2(
                sub_node, next_checked_bits, indent + 1, max_bit_n, offset
            )
    else:
        print(pfx + format_instruction(ins, max_bit_n))
