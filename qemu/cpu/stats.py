__all__ = [
    "compute_instruction_tree_stats"
  , "print_instruction_tree"
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
