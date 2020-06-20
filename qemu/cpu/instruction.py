__all__ = [
#   InstructionField
        "Operand"
      , "Opcode"
      , "Reserved"
  , "re_disas_format"
  , "Instruction"
]

from .constants import (
    BYTE_BITSIZE,
)
from collections import (
    OrderedDict,
)
from common import (
    lazy,
)
from copy import (
    deepcopy,
)
from re import (
    compile,
)
from six import (
    integer_types,
)


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
    callable object which must return list of function body tree elements that
    describe the semantics of the instruction
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
        self.semantics = kw_args.get("semantics", lambda : [])

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
