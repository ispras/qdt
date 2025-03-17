__all__ = [
    "InstructionEncoding"
  , "separate_instructions"
]

from common import (
    lazy,
)
from .constants import (
    SUPPORTED_READ_BITSIZES,
)
from .instruction import (
    build_instruction_tree,
    check_unreachable_instructions,
    InstructionTreeNode,
)

from collections import (
    defaultdict,
)


def separate_instructions(instructions):
    encodings = defaultdict(list)

    for i in instructions:
        encodings[i.encoding].append(i)

    return dict((
        (ie.name, ie)
            for ie in map(InstructionEncoding, encodings.values())
    ))


class InstructionEncoding(object):

    def __init__(self, instructions):
        self.instructions = instructions

    @lazy
    def name(self):
        return self.instructions[0].encoding

    def build_tree(self, read_bitsize, **opts):
        self.tree = node = InstructionTreeNode()
        build_instruction_tree(node, self.instructions, read_bitsize, **opts)
        check_unreachable_instructions(self.instructions)
        fill_tree_reading_seq(node, read_bitsize)

    def __lt__(self, enc):
        return self.name < enc.name


def fill_tree_reading_seq(node, read_bitsize, already_read=0):
    ins = node.instruction
    limit_read = node.limit_read
    del node.limit_read

    if ins:
        node.reading_seq = calc_node_reading_seq(ins.bitsize, already_read,
            limit_read
        )
    else:
        bitoffset, bitsize = node.interval

        reading_seq = calc_node_reading_seq(bitoffset + bitsize, already_read,
            limit_read
        )

        if reading_seq:
            node.reading_seq = reading_seq
            already_read = reading_seq[-1][0] + reading_seq[-1][1]

        for subnode in node.subtree.values():
            fill_tree_reading_seq(subnode, read_bitsize, already_read)


def calc_node_reading_seq(need_read, already_read, limit_read):
    if need_read <= already_read:
        return []

    result = []

    for r_bitsize in SUPPORTED_READ_BITSIZES:
        while (    need_read > already_read
               and already_read + r_bitsize <= limit_read
        ):
            result.append((already_read, r_bitsize))
            already_read += r_bitsize

    return result
