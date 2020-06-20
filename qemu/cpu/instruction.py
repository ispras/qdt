__all__ = [
#   InstructionField
        "Operand"
      , "Opcode"
      , "Reserved"
  , "Instruction"
]

from collections import (
    OrderedDict,
)
from common import (
    lazy,
)
from six import (
    integer_types,
)


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

    # TODO: it could be `lazy` `fields`, after excluding the `read_size`
    #       parameter
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

    @lazy
    def length(self):
        return sum(len(field) for field in self.fields)

    def __len__(self):
        return self.length

    def get_opcode_part(self, interval):
        offset, length = interval
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

    def iter_operand_parts(self):
        operands_dict = OrderedDict()

        for f in self.fields:
            if isinstance(f, Operand):
                operands_dict.setdefault(f.name, []).append(f)

        for name, parts in operands_dict.items():
            yield name, sorted(parts, key = lambda x: (x.num, x.subnum))
