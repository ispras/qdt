__all__ = [
    "InstructionEncoding"
  , "separate_instructions"
]

from common import (
    ee,
    lazy,
)
from .constants import (
    SUPPORTED_READ_BITSIZES,
)
from .instruction import (
    build_instruction_tree,
    DEFAULT_ENCODING_NAME,
    InstructionTreeNode,
)
from .stats import (
    check_unreachable_instructions,
    print_instruction_tree,
    print_instruction_tree2,
)
from source import (
    CIdGen,
)

from collections import (
    defaultdict,
)
from itertools import (
    starmap,
)
from re import (
    compile,
)


PRINT_INSTRUCTION_TREE = ee("QDT_PRINT_INSTRUCTION_TREE", "0")

re_encoding_sep = compile(r" +")
split_encoding_names = re_encoding_sep.split


def separate_instructions(instructions):
    encodings = defaultdict(list)

    for i in instructions:
        for encoding in split_encoding_names(i.encoding):
            encodings[encoding].append(i)

    return dict((
        (ie.name, ie)
            for ie in starmap(InstructionEncoding, encodings.items())
    ))


class InstructionEncoding(object):

    def __init__(self, name, instructions):
        self.name = name
        self.instructions = instructions

    @lazy
    def func_sfx(self):
        return CIdGen.generate(self.name).instance

    def build_tree(self, read_bitsize, **opts):
        self.tree = node = InstructionTreeNode()
        build_instruction_tree(node, self.instructions, read_bitsize, **opts)
        check_unreachable_instructions(node, self.instructions)
        if PRINT_INSTRUCTION_TREE:
            print("Encoding: " + self.name)
            {
                2: print_instruction_tree2
            }.get(
                PRINT_INSTRUCTION_TREE, print_instruction_tree
            )(node)
        fill_tree_reading_seq(node, read_bitsize)

    def __lt__(self, enc):
        # Default encoding is to be placed first in generated code.
        if self.name == DEFAULT_ENCODING_NAME:
            return True
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
