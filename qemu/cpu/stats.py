__all__ = [
    "compute_instruction_tree_stats"
  , "print_instruction_tree"
  , "format_instruction"
  , "format_instructions"
  , "print_instructions"
  , "check_unreachable_instructions"
]

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
