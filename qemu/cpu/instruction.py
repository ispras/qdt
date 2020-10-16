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


SHOW_INTERSECTION_WARNINGS = ee("QDT_SHOW_INTERSECTION_WARNINGS")


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


def common_bits_for_opcodes(instructions):
    "Finds bit numbers occupied by opcodes in all instructions."

    return instructions[0].opcode_bits.intersection(
        *[i.opcode_bits for i in instructions[1:]]
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


def highlight_interval(string, interval):
    "Marks interval in string with curly braces."

    bitoffset, bitsize = interval
    start = bitoffset
    end = bitoffset + bitsize
    return string[:start] + "{" + string[start:end] + "}" + string[end:]


def build_instruction_tree(node, instructions, read_bitsize,
    checked_bits = set(),
    show_subtree_warnings = SHOW_INTERSECTION_WARNINGS
):
    min_bitsize = min(i.bitsize for i in instructions)
    # temporary info for reading sequence calculation
    node.limit_read = min_bitsize

    common_bits = common_bits_for_opcodes(instructions)
    unchecked_common_bits = common_bits - checked_bits
    unchecked_common_intervals = split_intervals(
        bits_to_intervals(unchecked_common_bits), read_bitsize
    )

    if len(instructions) == 1:
        i = instructions[0]

        for interval in unchecked_common_intervals:
            node.interval = interval
            infix = i.get_opcode_part(interval)
            node.subtree[infix] = n = InstructionTreeNode()
            node = n
            # temporary info for reading sequence calculation
            node.limit_read = min_bitsize

        node.instruction = i
        return

    # find out first distinguishable opcode interval
    for interval in unchecked_common_intervals:
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
        # other instructions. Try to find distinguishable interval by
        # accounting bits of those overlapping non-common intervals.

        # Note, this is for error formatting only.
        max_bitsize = max(i.bitsize for i in instructions)

        min_bitsize_bits = integer_set(0, min_bitsize)

        for i in instructions:
            for f in i.fields:
                field_bits = integer_set(f.bitoffset, f.bitsize)
                unchecked_bits = (field_bits - checked_bits) & min_bitsize_bits
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
                    # not found `interval` yet
                    continue
                # found `interval`
                break
            else:
                # not found `interval` yet
                continue
            # found `interval`
            break
        else:
            raise RuntimeError("Indistinguishable instructions "
                "(check instructions encoding):\n    " + "\n    ".join(
                    "{1:<{0}} {2}".format(max_bitsize, i.opcode_bits_string,
                        i.comment
                    ) for i in instructions
                )
            )

        potential_error = False

        for i1, i2 in combinations(instructions, 2):
            i1b = i1.opcode_bits
            i2b = i2.opcode_bits

            if not (i1b <= i2b or i1b >= i2b):
                potential_error = True
                break

        if potential_error:
            # TODO: The `priority` attribute is required by the instruction in
            #       order to be able to influence the instruction
            #       identification.
            print("""\
Potential error: arguments and opcodes intersect in instructions at several
  intervals (highlighted interval is selected to distinguish). Instruction
  description order and interval selection priority affects instruction
  identification:
    """ + "\n    ".join(
    "{1:<{0}} {2}".format(max_bitsize + 2, # 2 for highlighting
        highlight_interval(i.opcode_bits_string, interval),
        i.comment
    ) for i in instructions
)
            )

        if (not potential_error and show_subtree_warnings):
            # Do not show same warnings again during recursive calls
            show_subtree_warnings = False

            print("""\
Warning: arguments and opcodes intersect in instructions.
  Arguments cannot get values equal to opcodes in the highlighted interval.
  That are instructions with opcodes can be interpreted as a special case of
  instructions with arguments. If it's not, check instructions encoding:
    """ + "\n    ".join(
    "{1:<{0}} {2}".format(max_bitsize + 2, # 2 for highlighting
        highlight_interval(i.opcode_bits_string, interval),
        i.comment
    ) for i in instructions
)
            )

    node.interval = interval
    new_checked_bits = checked_bits | integer_set(*interval)

    subtree = defaultdict(list)

    for i in instructions:
        infix = i.get_opcode_part(interval)
        if infix is None:
            # Notes:
            # 1. `default` is a "case" of `switch` block in C (used latter)
            # 2. it's an alphabetic and is sorted after all other infixes whose
            #    consist of digits only
            infix = "default"
        subtree[infix].append(i)

    # Note, only infix order is matter now. Instructions with same infix
    # will be sorted by the corresponding next common infix during recursive
    # `build_instruction_tree` call.
    for infix, instructions in sorted(subtree.items()):
        node.subtree[infix] = n = InstructionTreeNode()
        build_instruction_tree(n, instructions, read_bitsize,
            checked_bits if infix == "default" else new_checked_bits,
            show_subtree_warnings = show_subtree_warnings
        )
