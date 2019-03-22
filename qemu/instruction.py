__all__ = [
#   InstructionField
        "Operand"
      , "Opcode"
      , "Reserved"
  , "Instruction"
  , "interval_to_bits"
]


from common import (
    lazy
)
from collections import (
    defaultdict,
    OrderedDict
)
from six import (
    integer_types
)
from itertools import (
    count
)


NON_OPCODE_BIT = "x"


def interval_to_bits(interval):
    "Converts interval to bit numbers."

    return set(range(interval[0], interval[0] + interval[1]))


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

:Param branch:
    flag marks a jump instruction

:Param disas_format:
    string that forms the disassembler output for this instruction

:Param comment:
    string to be inserted into the leaves of the instruction tree

:Param semantics:
    callable object which must return list of function body tree elements that
    describe the semantics of the instruction
    """

    existing_names = defaultdict(lambda : count(0))

    def __init__(self, mnemonic, *raw_fields, **kw_args):
        self.mnemonic = mnemonic
        self.name = "%s_%d" % (
            mnemonic, next(Instruction.existing_names[mnemonic])
        )

        self.fields = []
        self.raw_fields = raw_fields

        self.branch = kw_args.get("branch", False)
        self.disas_format = kw_args.get("disas_format", mnemonic)
        self.comment = kw_args.get("comment", self.disas_format)
        self.semantics = kw_args.get("semantics", lambda : [])

    def split_operands_fill_offsets(self, read_size):
        """ Splits operands which are not `read_size`-aligned. Fills offsets
        for all fields.
        """

        self.fields[:] = []
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
                    new_offset = (cur_offset // read_size + 1) * read_size
                    new_length = min(new_offset - cur_offset, length)

                    new_field = Operand(new_length, field.name,
                        num = field.num
                    )
                    new_field.subnum = subnum
                    new_field.offset = cur_offset

                    self.fields.append(new_field)

                    subnum += 1
                    length -= new_offset - cur_offset
                    cur_offset = new_offset
            else:
                field.offset = offset
                self.fields.append(field)

            offset += field.length

    def __eq__(self, other):
        return self.name == other.name

    def __len__(self):
        return sum(len(field) for field in self.fields)

    def get_opcode_part(self, pos):
        offset, length = pos
        res = self.string[offset:offset + length]
        if res.find(NON_OPCODE_BIT) != -1:
            return None
        return res

    @lazy
    def string(self):
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
                result = result | interval_to_bits((f.offset, f.length))
        return result

    @lazy
    def opcode_bits(self):
        return self.field_class_bits(Opcode)

    @lazy
    def operands_bits(self):
        return self.field_class_bits(Operand)

    def operand_parts(self):
        operands_dict = OrderedDict()

        for f in self.fields:
            if isinstance(f, Operand):
                operands_dict.setdefault(f.name, []).append(f)

        for name, parts in operands_dict.items():
            yield name, sorted(parts, key = lambda x: (x.num, x.subnum))
