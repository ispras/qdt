__all__ = [
#   InstructionField
        "Operand"
      , "Opcode"
      , "Reserved"
  , "Instruction"
  , "InstructionSet"
  , "parse_endian"
]

from copy import (
    copy
)
from sys import (
    stderr
)
from collections import (
    defaultdict
)
from six import (
    integer_types
)


BYTE_SIZE = 8


def parse_endian(string):
    res = string.lower()
    if res not in ["little", "big"]:
        raise ValueError("Wrong endianness option: " + string)
    return res == "big"


class InstructionField(object):

    def __init__(self, length, val = "0", num = 0):
        self.length = length
        self.val = val
        self.num = num

        self.start = 0
        self.end = 0

    def __len__(self):
        return self.length

    def check(self):
        return self.length == len(self.val) or not isinstance(self, Opcode)

    def dump(self):
        print(self.length, self.val, type(self).__name__)
        if self.check() is not True:
            stderr.write("Warning: check failed",
                "(" + str(self.length) + " " + str(len(self.val)) + ")"
            )


class Operand(InstructionField):

    def __init__(self, length, name, num = 0):
        super(Operand, self).__init__(length, name, num)

    def __str__(self):
        return "Operand(" + str(self.length) + ', "' + self.val + '")'


class Opcode(InstructionField):

    def __init__(self, length, val = None):
        if val is None:
            val = "0" * length
        elif isinstance(val, integer_types):
            bin_val = bin(val)[2:]
            val = "0" * max(0, length - len(bin_val)) + bin_val

        super(Opcode, self).__init__(length, val)

    def __str__(self):
        return "Opcode(" + str(self.length) + ", 0b" + self.val + ")"


class Reserved(InstructionField):

    def __init__(self, length):
        super(Reserved, self).__init__(length)

    def __str__(self):
        return "Reserved(" + str(self.length) + ")"


def expand_instruction(cur_iter, cur_path, res_list):
    """ Given instruction class as a prefix tree of opcodes, this function
recursively generates all instruction encoding variants as paths on the tree.
    """
    # TODO: is `cur_iter` the "prefix tree"? Improve the doc.
    # TODO: this function is given an iter of Instruction.args. So, what is
    # "instruction class"?
    try:
        cur = next(cur_iter)
    except StopIteration:
        res_list.append(cur_path)
    else:
        if isinstance(cur, InstructionField):
            expand_instruction(cur_iter, cur_path + [cur], res_list)
        else:
            # encoding varies here, an iterable is expected
            for br in cur:
                expand_instruction(iter(br), cur_path, res_list)


class Instruction(object):
    # TODO: A global API overview is required. Look the module for some
    # questions.

    def __init__(self, name, *args, **kw_args):
        # TODO: mnem mnem mnem
        self.mnem = name
        fields_dict = defaultdict(list)

        for a in args:
            if isinstance(a, Operand):
                # TODO: multiple Operands per a field? Or multiple fields per
                # operand?
                fields_dict[a.val].append(a)

        for k, l in fields_dict.items():
            # TODO: k? field?
            offset = 0
            l = sorted(l, key = lambda x: x.num)
            for j, f in enumerate(l):
                if f.num != j:
                    raise ValueError(
"Missed item #%d of field %s in the description of %s " % (j, k, name)
                    )
                f.start = offset
                f.end = offset + f.length - 1
                offset += f.length

        self.args = list(args) # TODO: is copying really needed?

        self.branch = kw_args.get("branch", False)

        # try to get format line for disassembler
        format_ = kw_args.get("format", name)
        self.format = format_

        self.comment = kw_args.get("comment", format_)

    def __str__(self):
        indent = 2
        tab = 4 * " "
        res = (tab * (indent - 1) + "Instruction(\n" + tab * indent + '"' +
            self.mnem + '",'
        )
        for a in self.args:
            res += "\n" + tab * indent + str(a) + ","
        if self.comment:
            res += "\n" + tab * indent + 'comment="' + self.comment + '",'
        res += "\n" + tab * (indent - 1) + "),\n"
        return res

    def __len__(self):
        result = 0
        for f in self.args:
            result += len(f)
        return result

    # TODO: fetch_size? Instruction fetching?
    def expand(self, read_size):
        res = []
        tmp = []
        expand_instruction(iter(self.args), [], tmp)
        for l in tmp:
            res.append(RawInstruction(
                self.mnem,
                read_size,
                self.comment,
                self.format,
                self.branch,
                *l
            ))
        return res


# TODO: Raw? It's looks like a processed one.
class RawInstruction(object):
    # TODO: some doc

    existing_names = defaultdict(int)

    @staticmethod
    def gen_unique_name(mnem):
        n = RawInstruction.existing_names[mnem]
        RawInstruction.existing_names[mnem] = n + 1
        return mnem + "_" + str(n)

    def __init__(self, name, read_size,
        comment = None,
        format = "",
        branch = False,
        *args
    ):
        self.name = RawInstruction.gen_unique_name(name)
        self.mnem = name
        self.fields = []
        self.parent = ""
        self.comment = comment
        self.format = format
        self.branch = branch

        offset = 0
        for arg in args:
            if isinstance(arg, InstructionField):
                new_args = []
                # split fields which are not byte-aligned
                # and further reverse the bytes if description is big endian
                # since we support only little endian x86 host
                if (   offset // read_size
                    != (offset + arg.length - 1) // read_size
                ):
                    # TODO: extract this predicate to the top?
                    if not isinstance(arg, Operand):
                        # TODO: offset += ... ?
                        self.add_field(arg)
                        continue

                    # TODO: a comment about what this code does (tries to do)
                    # TODO: "cur"? maybe "rest" (length)?
                    cur = arg.length - 1
                    cur_off = offset
                    shift = arg.start
                    while cur >= 0:
                        # TODO: shift is not adjusted. Is this alg correct?
                        # TODO: this code should be refactored to be more clear
                        new_arg = copy(arg)
                        # TODO: end is not assigned to new_arg.end
                        end = (cur_off // read_size + 1) * read_size
                        new_arg.start = (max(0, cur - (end - cur_off) + 1) +
                            shift
                        )
                        new_arg.end = cur + shift
                        new_arg.length = min(end - cur_off, cur + 1)

                        new_args.append(new_arg)
                        cur -= end - cur_off
                        cur_off = end

                    cur_off = arg.length - 1

                    for a in new_args[::-1]:
                        a.end = cur_off + shift
                        a.start = cur_off - a.length + 1 + shift
                        cur_off -= a.length

                    for a in new_args:
                        self.add_field(a)
                else:
                    self.add_field(arg)

                offset += arg.length

            elif isinstance(arg, str):
                # TODO: what is a "parent" of an instruction?
                self.parent = arg

        # TODO: a lazy property?
        self.string = self.get_string()

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        if self.parent != "":
            # TODO: it's strange. what is this hashing principle?
            return self.parent.__hash__()
        else:
            return self.mnem.__hash__()

    def __len__(self):
        res = 0
        for field in self.fields:
            res += len(field)
        return res

    def __str__(self):
        indent = 2
        tab = 4 * " "
        res = (tab * (indent - 1) + "Instruction(\n" + tab * indent + '"' +
            self.mnem + '",'
        )
        for f in self.fields:
            res += "\n" + tab * indent + str(f) + ","
        if self.comment:
            res += "\n" + tab * indent + 'comment="' + self.comment + '",'
        res += "\n" + tab * (indent - 1) + "),\n"
        return res

    def add_field(self, field):
        self.fields.append(field)

    def get_field(self, offset, length):
        # TODO: is it better to specify just an offset and look for a field
        # overlapping it?
        cur_off = 0
        for f in self.fields:
            if f.length == length and cur_off == offset:
                return f
            cur_off += f.length
        return None

    def dump(self, verbose = False):
        print("INSTRUCTION: " + self.mnem + "(" + self.parent + ")")
        if verbose:
            for field in self.fields:
                field.dump()

    def get_full_opcode(self):
        "opcode is a list of tuples: [(val_1, len_1), ..., (val_k, len_k)]"
        res = []
        offset = 0
        for field in self.fields:
            if isinstance(field, Opcode):
                res.append((field.val, offset))
            offset += len(field)
        return res

    def get_opcode_part(self, pos):
        offset, length = pos
        res = self.string[offset:offset + length]
        # TODO: what "x" means? a doc is required
        if res.find("x") != -1:
            return None
        return res

    def has_opcode(self, offset, length):
        return self.string[offset:offset + length].find("x") == -1

    def get_string(self):
        length = len(self)
        opc = self.get_full_opcode()
        res = list("x" * length)
        for val, off in opc:
            i = 0
            stop = False
            for c in val:
                if i + off >= length:
                    break
                res[i + off] = c
                if stop:
                    break
                i += 1
        return "".join(res)


class InstructionSet(object):

    def __init__(self,
        name_to_format = None,
        instr_list = None,
        endianess = "little",
        read_size = 1
    ):
        # TODO: some doc
        self.name_to_format = {} if name_to_format is None else name_to_format
        self.instruction_list = [] if instr_list is None else instr_list
        self.desc_bigendian = parse_endian(endianess)
        self.read_size = read_size
