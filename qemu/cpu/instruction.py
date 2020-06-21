__all__ = [
#   InstructionField
        "Operand"
      , "Opcode"
      , "Reserved"
  , "Instruction"
  , "build_instruction_tree_root"
]

from collections import (
    OrderedDict,
    defaultdict,
)
from common import (
    ee,
    lazy,
)
from itertools import (
    combinations,
)
from six import (
    integer_types,
)


SHOW_INTERSECTION_WARNINGS = ee("QDT_SHOW_INTERSECTION_WARNINGS")


NON_OPCODE_BIT = "x"


def integer_set(offset, length):
    "Converts interval to bit numbers."

    return set(range(offset, offset + length))


class InstructionField(object):

    def __init__(self, length):
        self.length = length

    def __len__(self):
        return self.length


class Operand(InstructionField):

    def __init__(self, length, name, num = 0):
        super(Operand, self).__init__(length)

        self.name = name

        # user defined operand part number
        self.num = num

        # splitted operand part number
        self.subnum = 0

        # offset in instruction
        self.offset = 0


class Opcode(InstructionField):

    def __init__(self, length, val = None):
        super(Opcode, self).__init__(length)

        if val is None:
            val = "0" * length
        elif isinstance(val, integer_types):
            val = "{1:0{0}b}".format(length, val)

        if len(val) > length:
            raise RuntimeError("Opcode value does not fit in available length")

        self.val = val


class Reserved(InstructionField):
    pass


class Instruction(object):
    """ This class store information about one instruction.

:param branch:
    flag marks a jump instruction

:param disas_format:
    string that forms the disassembler output for this instruction

:param comment:
    string to be inserted into the leaves of the instruction tree

:param semantics:
    callable object which must return list of function body tree elements that
    describe the semantics of the instruction
    """

# TODO: an ASCII-art schematic with field layout (bit enumeration) relative to
#       first byte of the instruction & other fields

    def __init__(self, mnemonic, *raw_fields, **kw_args):
        self.mnemonic = mnemonic
        self.fields = []
        self.raw_fields = raw_fields

        self.branch = kw_args.get("branch", False)
        self.disas_format = kw_args.get("disas_format", mnemonic)
        self.comment = kw_args.get("comment", self.disas_format)
        self.semantics = kw_args.get("semantics", lambda : [])

    # TODO: it could be `lazy` `fields`.
    def split_operands_fill_offsets(self, read_size):
        """ Splits operands that cross read boundaries (defined by
        `read_size`). Fills offsets for all fields.
        """

        del self.fields[:]
        offset = 0
        for field in self.raw_fields:
            if (    isinstance(field, Operand)
                and (offset // read_size !=
                    (offset + field.length - 1) // read_size
                )
            ):
                length = field.length
                cur_offset = offset
                subnum = 0
                while length > 0:
                    next_offset = (cur_offset // read_size + 1) * read_size
                    field_length = min(next_offset - cur_offset, length)

                    new_field = Operand(field_length, field.name,
                        num = field.num
                    )
                    new_field.subnum = subnum
                    new_field.offset = cur_offset

                    self.fields.append(new_field)

                    subnum += 1
                    length -= field_length
                    cur_offset = next_offset
            else:
                field.offset = offset
                self.fields.append(field)

            offset += field.length

    def __len__(self):
        # TODO: defile & use `lazy` length
        return sum(len(field) for field in self.fields)

    def get_opcode_part(self, pos):
        # XXX: can a `length` be encapsulated in a `pos`ition?
        offset, length = pos
        res = self.opcode_bits_string[offset:offset + length]
        if NON_OPCODE_BIT in res:
            return None
        return res

    @lazy
    def opcode_bits_string(self):
        res = [NON_OPCODE_BIT] * len(self)
        for f in self.fields:
            if isinstance(f, Opcode):
                for i, c in enumerate(f.val, f.offset):
                    res[i] = c
        return "".join(res)

    def field_class_bits(self, class_):
        result = set()
        for f in self.fields:
            if isinstance(f, class_):
                result |= integer_set(f.offset, f.length)
        return result

    @lazy
    def opcode_bits(self):
        return self.field_class_bits(Opcode)

    @lazy
    def operand_bits(self):
        return self.field_class_bits(Operand)

    # XXX: iter_operand_parts
    def operand_parts(self):
        operands_dict = OrderedDict()

        for f in self.fields:
            if isinstance(f, Operand):
                operands_dict.setdefault(f.name, []).append(f)

        for name, parts in operands_dict.items():
            yield name, sorted(parts, key = lambda x: (x.num, x.subnum))


class InstructionTreeNode(object):

    def __init__(self, opcode = None):
        self.instruction = None
        self.opcode = opcode
        self.subtree = OrderedDict()
        self.reads_desc = []


def common_bits_for_opcodes(instructions):
    "Finds bit numbers occupied by opcodes in all instructions."

    return instructions[0].opcode_bits.intersection(
        *[i.opcode_bits for i in instructions[1:]]
    )


def bits_to_intervals(bits):
    """ Converts bit numbers to bit intervals.

:returns: list of tuples: [(off_1, len_1), ..., (off_k, len_k), ...]
    """

    if not bits:
        return []

    bit_numbers = sorted(bits)
    result = []
    offset = prev_bit = bit_numbers[0]
    length = 1

    for bit in bit_numbers[1:]:
        if bit - prev_bit == 1:
            length += 1
        else:
            result.append((offset, length))
            offset = bit
            length = 1

        prev_bit = bit

    result.append((offset, length))
    return result


def split_intervals(intervals, read_size):
    "Splits intervals by read_size."

    new_intervals = []

    for i in intervals:
        cur_offset, length = i

        if (cur_offset // read_size != (cur_offset + length - 1) // read_size):
            while length > 0:
                new_offset = (cur_offset // read_size + 1) * read_size
                new_length = min(new_offset - cur_offset, length)

                new_intervals.append((cur_offset, new_length))

                length -= new_offset - cur_offset
                cur_offset = new_offset
        else:
            new_intervals.append(i)

    return new_intervals


def build_instruction_tree(node, instructions, read_size, checked_bits,
    show_subtree_warnings = True
):
    min_len = min(len(i) for i in instructions)
    # temporary info for reads description calculation
    node.limit_read = min_len

    common_bits = common_bits_for_opcodes(instructions)
    # TODO: unchecked_common_bits
    unchecked_bits = common_bits - checked_bits
    # TODO: unchecked_common_intervals
    unchecked_opcs = split_intervals(
        bits_to_intervals(unchecked_bits), read_size
    )

    for opc in unchecked_opcs:
        # TODO: no need to iterate all `instructions`, stop on first differing
        opcs = [i.get_opcode_part(opc) for i in instructions]

        if len(set(opcs)) > 1:
            break
    else:
        if len(instructions) == 1:
            i = instructions[0]

            for opc in unchecked_opcs:
                node.opcode = opc
                key = i.get_opcode_part(opc)
                node.subtree[key] = n = InstructionTreeNode()
                node = n
                # temporary info for reads description calculation
                node.limit_read = min_len

            node.instruction = i
            return
        else:
            max_len = max(len(i) for i in instructions)
            min_len_bits = integer_set(0, min_len)

            for i in instructions:
                for f in i.fields:
                    field_bits = integer_set(f.offset, f.length)
                    unchecked_bits = (field_bits - checked_bits) & min_len_bits
                    unchecked_opcs = split_intervals(
                        bits_to_intervals(unchecked_bits), read_size
                    )

                    # XXX: dead code, see `else` block of `for` below
                    if not unchecked_opcs:
                        continue

                    for opc in unchecked_opcs:
                        # TODO: no need to iterate all `instructions` here too
                        opcs = [j.get_opcode_part(opc) for j in instructions]

                        if len(set(opcs)) > 1:
                            break
                    else:
                        # not found `opc` yet
                        continue
                    # found `opc`
                    break
                else:
                    # not found `opc` yet
                    continue
                # found `opc`
                break
            else:
                # XXX: indistinguishable instructions?
                raise RuntimeError("Unresolved conflict in instructions:"
                    "\n    " + "\n    ".join(
                        "{1:<{0}} {2}".format(max_len, i.opcode_bits_string,
                            i.comment
                        ) for i in instructions
                    )
                )

            pe_flag = False

            for i1, i2 in combinations(instructions, 2):
                i1b = i1.opcode_bits
                i2b = i2.opcode_bits

                if not (i1b <= i2b or i1b >= i2b):
                    pe_flag = True
                    break

            if pe_flag:
                # XXX: There is no explicit parse tree. Better say that
                #      instruction description order affects instruction
                #      identification. Probably, not only description order
                #      affects that. Also, what about description order and
                #      priority during identification?
                print("Potential error: bit check order affects instruction"
                    " parse tree for instructions:\n    " + "\n    ".join(
                        "{1:<{0}} {2}".format(max_len, i.opcode_bits_string,
                            i.comment
                        ) for i in instructions
                    )
                )

            if (not pe_flag
                and show_subtree_warnings
                and SHOW_INTERSECTION_WARNINGS
            ):
                # XXX: The point is not intersection itself. Arguments can
                #      got values equal to opcodes in corresponding intervals
                #      that makes instructions indistinguishable. It probably
                #      results in incorrect instruction identification.
                print("Warning: arguments and opcode intersect in instructions"
                    ":\n    " + "\n    ".join(
                        "{1:<{0}} {2}".format(max_len, i.opcode_bits_string,
                            i.comment
                        ) for i in instructions
                    )
                )

            show_subtree_warnings = False

    node.opcode = opc
    new_checked_bits = checked_bits | integer_set(*opc)

    subtree = defaultdict(list)

    for i in instructions:
        key = i.get_opcode_part(opc)
        if key is None:
            key = "default"
        subtree[key].append(i)

    for key, instructions in sorted(subtree.items()):
        node.subtree[key] = n = InstructionTreeNode()
        build_instruction_tree(n, instructions, read_size,
            checked_bits if key == "default" else new_checked_bits,
            show_subtree_warnings = show_subtree_warnings
        )


def build_instruction_tree_root(instructions, read_size):
    node = InstructionTreeNode()
    build_instruction_tree(node, instructions, read_size, set())
    return node
