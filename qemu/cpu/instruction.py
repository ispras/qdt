__all__ = [
#   InstructionField
        "Operand"
      , "Opcode"
      , "Reserved"
  , "re_disas_format"
  , "Instruction"
  , "InstructionTreeNode"
  , "build_instruction_tree"
]

from .constants import (
    BYTE_BITSIZE,
)
from collections import (
    OrderedDict,
    defaultdict,
)
from common import (
    ee,
    lazy,
)
from copy import (
    deepcopy,
)
from itertools import (
    combinations,
)
from re import (
    compile,
)
from six import (
    integer_types,
)


DEBUG_BUILD_INSTRUCTION_TREE = ee("QDT_DEBUG_BUILD_INSTRUCTION_TREE")


NON_OPCODE_BIT = "x"


class InstructionDescriptionError(RuntimeError):
    pass


def integer_set(bitoffset, bitsize):
    "Converts interval to bit numbers."

    return set(range(bitoffset, bitoffset + bitsize))


def iter_split_interval(interval, read_bitsize):
    "Splits the interval by read_bitsize."

    cur_bitoffset, bitsize = interval

    if (cur_bitoffset // read_bitsize !=
        (cur_bitoffset + bitsize - 1) // read_bitsize
    ):
        while bitsize > 0:
            next_bitoffset = (
                (cur_bitoffset // read_bitsize + 1) * read_bitsize
            )
            interval_bitsize = min(next_bitoffset - cur_bitoffset, bitsize)

            yield cur_bitoffset, interval_bitsize

            bitsize -= interval_bitsize
            cur_bitoffset = next_bitoffset
    else:
        yield cur_bitoffset, bitsize


class InstructionField(object):

    def __init__(self, bitsize):
        self.bitsize = bitsize


class Operand(InstructionField):

    def __init__(self, bitsize, name,
        num = 0,
        # Note, the following parameters are for internal usage only.
        subnum = 0,
        bitoffset = 0
    ):
        super(Operand, self).__init__(bitsize)

        self.name = name

        # user defined operand part number
        self.num = num

        # splitted operand part number
        self.subnum = subnum

        # bitoffset in instruction
        self.bitoffset = bitoffset


class Opcode(InstructionField):

    def __init__(self, bitsize, val = None):
        super(Opcode, self).__init__(bitsize)

        if val is None:
            val = "0" * bitsize
        elif isinstance(val, integer_types):
            val = "{1:0{0}b}".format(bitsize, val)

        if len(val) > bitsize:
            raise InstructionDescriptionError(
                "Opcode value does not fit in available bitsize"
            )

        self.val = val


class Reserved(InstructionField):
    pass


re_disas_format = compile("<(.+?)>|([^<>]+)")

def no_semantics(function, source):
    return []

class Instruction(object):
    """ This class store information about one instruction.

:param branch:
    flag marks a control flow branching instruction

:param disas_format:
    string that describes the disassembler output for this instruction

:param comment:
    string to be inserted into the generated semantic boilerplate code (the
    leaves of the instruction tree)

:param semantics:
    callable object which gets `Function` and source containing the
    function, and must return list of function body tree elements that
    describe the semantics of the instruction (see `no_semantics` example)

:param priority:
    number that determines which instruction will be selected if the encoding
    matches multiple instructions
    """

# TODO: an ASCII-art schematic with field layout (bit enumeration) relative to
#       first byte of the instruction & other fields

    def __init__(self, mnemonic, *raw_fields, **kw_args):
        self.mnemonic = mnemonic
        # `InstructionField` objects can be reused while defining similar
        # instructions. As we going to modify them, the fields must be copied.
        self.raw_fields = deepcopy(raw_fields)

        self.branch = kw_args.get("branch", False)
        self.disas_format = kw_args.get("disas_format", mnemonic)
        self.comment = kw_args.get("comment", self.disas_format)
        self.semantics = kw_args.get("semantics", no_semantics)
        self.priority =  kw_args.get("priority", 0)

    @lazy
    def bitsize(self):
        return sum(field.bitsize for field in self.fields)

    @lazy
    def fields(self):
        return self.split_operands_fill_bitoffsets()

    def split_operands_fill_bitoffsets(self):
        """ Splits operands that cross read boundaries (defined by
        `read_bitsize`). Fills bitoffsets for all fields.
        """

        read_bitsize = self.read_bitsize
        fields = []
        bitoffset = 0
        for field in self.raw_fields:
            bitsize = field.bitsize
            if isinstance(field, Operand):
                for subnum, (field_bitoffset, field_bitsize) in enumerate(
                    iter_split_interval((bitoffset, bitsize), read_bitsize)
                ):
                    fields.append(
                        Operand(field_bitsize, field.name,
                            num = field.num,
                            subnum = subnum,
                            bitoffset = field_bitoffset
                        )
                    )
            else:
                field.bitoffset = bitoffset
                fields.append(field)
            bitoffset += bitsize

        if bitoffset % read_bitsize:
            raise InstructionDescriptionError(
                'The instruction "%s" is not aligned by read_size %d' % (
                    self.comment, self.read_bitsize // BYTE_BITSIZE
                )
            )

        return tuple(fields)

    def get_opcode_part(self, interval):
        bitoffset, bitsize = interval
        res = self.opcode_bits_string[bitoffset:bitoffset + bitsize]
        if NON_OPCODE_BIT in res:
            return None
        return res

    @lazy
    def opcode_bits_string(self):
        res = [NON_OPCODE_BIT] * self.bitsize
        for f in self.fields:
            if isinstance(f, Opcode):
                for i, c in enumerate(f.val, f.bitoffset):
                    res[i] = c
        return "".join(res)

    def field_class_bits(self, class_):
        result = set()
        for f in self.fields:
            if isinstance(f, class_):
                result |= integer_set(f.bitoffset, f.bitsize)
        return result

    @lazy
    def opcode_bits(self):
        return self.field_class_bits(Opcode)

    @lazy
    def opcode_boundaries(self):
        "Bit numbers where opcode intervals start or end"

        boundaries = set()
        for interval in bits_to_intervals(self.opcode_bits):
            bitoffset, bitsize = interval
            boundaries.add(bitoffset)
            boundaries.add(bitoffset + bitsize)
        return boundaries

    @lazy
    def non_opcode_bits(self):
        return integer_set(0, self.bitsize) - self.opcode_bits

    @lazy
    def operand_bits(self):
        return self.field_class_bits(Operand)

    def iter_operand_parts(self):
        operands_dict = OrderedDict()

        for f in self.fields:
            if isinstance(f, Operand):
                operands_dict.setdefault(f.name, []).append(f)

        for name, parts in operands_dict.items():
            yield name, sorted(parts, key = lambda x: (x.num, x.subnum))


class InstructionTreeNode(object):

    def __init__(self, interval = None):
        self.instruction = None
        self.interval = interval
        self.subtree = OrderedDict()
        self.reading_seq = []

    def __eq__(self, other):
        if self.instruction:
            return self.instruction == other.instruction
        else:
            if other.instruction:
                return False

        if self.interval != other.interval:
            return False

        if self.subtree.keys() != other.subtree.keys():
            return False

        for i, j in zip(self.subtree.items(), other.subtree.items()):
            if i != j:
                return False

        return True


def common_bits_for_opcodes(instructions):
    "Finds bit numbers occupied by opcodes in all instructions."

    return instructions[0].opcode_bits.intersection(
        *[i.opcode_bits for i in instructions[1:]]
    )


def all_bits_for_opcodes(instructions):
    "Finds bit numbers occupied by opcodes in any of the instructions."

    return instructions[0].opcode_bits.union(
        *[i.opcode_bits for i in instructions[1:]]
    )


def all_bits_for_non_opcodes(instructions):
    "Finds bit numbers not occupied by opcodes in any of the instructions."

    return instructions[0].non_opcode_bits.union(
        *[i.non_opcode_bits for i in instructions[1:]]
    )


def all_opcode_boundaries(instructions):
    return instructions[0].opcode_boundaries.union(
        *[i.opcode_boundaries for i in instructions[1:]]
    )


def bits_to_intervals(bits):
    """ Converts bit numbers to bit intervals.

:returns: list of tuples: [(bitoffset_0, bitsize_0), ...]
    """

    if not bits:
        return []

    bit_numbers = sorted(bits)
    result = []
    bitoffset = prev_bit = bit_numbers[0]
    bitsize = 1

    for bit in bit_numbers[1:]:
        if bit - prev_bit == 1:
            bitsize += 1
        else:
            result.append((bitoffset, bitsize))
            bitoffset = bit
            bitsize = 1

        prev_bit = bit

    result.append((bitoffset, bitsize))
    return result


def split_intervals(intervals, read_bitsize):
    "Splits intervals by read_bitsize."

    splitted_intervals = []
    for i in intervals:
        splitted_intervals.extend(iter_split_interval(i, read_bitsize))
    return splitted_intervals


def split_intervals_by_boundaries(intervals, boundaries):
    """ Splits every interval by every boundary
:param intervals:
    list of intervals
:param boundaries:
    set of boundaries
    """

    boundaries = sorted(list(boundaries))
    splitted_intervals = []
    for i in intervals:
        bitoffset, bitsize = i
        interval_end = bitoffset + bitsize
        for b in boundaries:
            if b <= bitoffset:
                continue
            if b >= interval_end:
                break
            splitted_intervals.append((bitoffset, b - bitoffset))
            bitoffset = b
        splitted_intervals.append((bitoffset, interval_end - bitoffset))
    return splitted_intervals


def highlight_interval(string, interval):
    "Marks interval in string with curly braces."

    bitoffset, bitsize = interval
    start = bitoffset
    end = bitoffset + bitsize
    return string[:start] + "{" + string[start:end] + "}" + string[end:]


def build_subtree_for_instruction(node, i, read_bitsize, checked_bits):
    min_bitsize = i.bitsize
    # temporary info for reading sequence calculation
    node.limit_read = min_bitsize

    unchecked_bits = i.opcode_bits - checked_bits
    unchecked_intervals = split_intervals(
        bits_to_intervals(unchecked_bits), read_bitsize
    )

    for interval in unchecked_intervals:
        node.interval = interval
        infix = i.get_opcode_part(interval)
        node.subtree[infix] = n = InstructionTreeNode()
        node = n
        # temporary info for reading sequence calculation
        node.limit_read = min_bitsize

    node.instruction = i


def build_instruction_tree(node, instructions, read_bitsize,
    checked_bits = set(),
    depth = 0 # for debugging purposes
):
    # Note, this is for formatting only.
    max_bitsize = max(i.bitsize for i in instructions)

    if DEBUG_BUILD_INSTRUCTION_TREE:
        print("DEBUG: Instructions (depth %d):\n" % depth + "\n".join(
            "{1:<{0}} {2}".format(
                max_bitsize,
                i.opcode_bits_string,
                i.comment
            ) for i in instructions
        ))

    if len(instructions) == 1:
        build_subtree_for_instruction(
            node, instructions[0], read_bitsize, checked_bits
        )
        return

    min_bitsize = min(i.bitsize for i in instructions)
    # temporary info for reading sequence calculation
    node.limit_read = min_bitsize

    # First approach: try to find distinguishable interval among the bits that
    # are opcodes for all instructions
    common_bits = common_bits_for_opcodes(instructions)
    unchecked_bits = common_bits - checked_bits
    unchecked_intervals = split_intervals(
        bits_to_intervals(unchecked_bits), read_bitsize
    )

    for interval in unchecked_intervals:
        instructions_iter = iter(instructions)
        opc = next(instructions_iter).get_opcode_part(interval)
        for i in instructions_iter:
            if i.get_opcode_part(interval) != opc:
                # found `interval`
                break
        else:
            # not found `interval` yet
            continue
        # found `interval`
        break
    else:
        # Given `instructions` have equal opcodes in intervals being checked.
        # Opcodes of some instructions may overlap non-opcode fields of
        # other instructions.
        # Second approach: try to find distinguishable interval by
        # accounting bits of those overlapping non-common intervals.

        min_bitsize_bits = integer_set(0, min_bitsize)
        opcode_bits = all_bits_for_opcodes(instructions)
        non_opcode_bits = all_bits_for_non_opcodes(instructions)
        unchecked_bits = (
            (opcode_bits & non_opcode_bits - checked_bits) & min_bitsize_bits
        )

        # Splitting by the boundaries of opcodes ensures that in each interval
        # there will be strictly either opcodes or non-opcodes.
        boundaries = all_opcode_boundaries(instructions)

        unchecked_intervals = split_intervals_by_boundaries(
            split_intervals(bits_to_intervals(unchecked_bits), read_bitsize),
            boundaries
        )

        for interval in unchecked_intervals:
            instructions_iter = iter(instructions)
            opc = next(instructions_iter).get_opcode_part(interval)
            for i in instructions_iter:
                if i.get_opcode_part(interval) != opc:
                    # found `interval`
                    break
            else:
                # not found `interval` yet
                continue
            # found `interval`
            break
        else:
            # No intervals left to distinguish instructions.
            # Third approach: select the instruction whose opcode is a superset
            # for the rest.

            no_superset = False
            superset_i = instructions[0]

            for i in instructions[1:]:
                superset_b = superset_i.opcode_bits
                i_b = i.opcode_bits
                if superset_b <= i_b:
                    superset_i = i
                elif not (i_b <= superset_b):
                    no_superset = True
                    break

            if not no_superset:
                build_subtree_for_instruction(
                    node, superset_i, read_bitsize, checked_bits
                )
                return
            else:
                # No instruction with superset opcode.
                # Fourth approach: select the instruction with the highest
                # `priority`.

                instructions_by_priority = defaultdict(list)
                for i in instructions:
                    instructions_by_priority[i.priority].append(i)

                max_priority = max(instructions_by_priority.keys())
                instrs_with_max_priority = instructions_by_priority[max_priority]

                if len(instrs_with_max_priority) == 1:
                    build_subtree_for_instruction(
                        node, instrs_with_max_priority[0], read_bitsize, checked_bits
                    )
                    return
                else:
                    raise RuntimeError("Indistinguishable instructions "
                        "(check instructions encoding or priority):\n    " +
                        "\n    ".join(
                            "{1:<{0}} (priority {2}) {3}".format(
                                max_bitsize,
                                i.opcode_bits_string,
                                i.priority,
                                i.comment
                            ) for i in sorted(
                                instructions,
                                key = lambda i: i.priority,
                                reverse = True
                            )
                        )
                    )

    if DEBUG_BUILD_INSTRUCTION_TREE:
        print("{1:<{0}} chosed interval ({2}, {3})".format(
            max_bitsize,
            "".join(
                ["-"] * interval[0] +
                ["C"] * interval[1] +
                ["-"] * (min_bitsize - interval[0] - interval[1])
            ),
            interval[0],
            interval[1]
        ))

    node.interval = interval

    subtree = defaultdict(list)
    non_opcode_instructions = []

    for i in instructions:
        infix = i.get_opcode_part(interval)
        if infix is None:
            non_opcode_instructions.append(i)
            continue
        subtree[infix].append(i)

    if len(non_opcode_instructions) > 0:
        for infix, instructions in subtree.items():
            instructions.extend(non_opcode_instructions)
        # Notes:
        # 1. `default` is a "case" of `switch` block in C (used latter)
        # 2. it's an alphabetic and is sorted after all other infixes whose
        #    consist of digits only
        subtree["default"] = non_opcode_instructions

    # Note, only infix order is matter now. Instructions with same infix
    # will be sorted by the corresponding next common infix during recursive
    # `build_instruction_tree` call.
    for infix, instructions in sorted(subtree.items()):
        node.subtree[infix] = n = InstructionTreeNode()
        build_instruction_tree(n, instructions, read_bitsize,
            checked_bits | integer_set(*interval),
            depth = depth + 1
        )

    # Elimination of same subtrees
    # TODO: now subtrees are removed only if each completely matches with
    # "default" subtree, add support for joining only some subtrees
    try:
        subtree_node = node.subtree["default"]
    except KeyError:
        pass
    else:
        for s in node.subtree.values():
            if s is subtree_node:
                continue
            if s != subtree_node:
                break
        else:
            node.instruction = subtree_node.instruction
            node.interval = subtree_node.interval
            node.subtree = subtree_node.subtree
