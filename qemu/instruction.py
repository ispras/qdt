__all__ = [
#   InstrField
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


BYTE_SIZE = 8


def parse_endian(string):
    res = string.lower()
    if res not in ["little", "big"]:
        raise ValueError("Wrong endianness option: " + string)
    return res == "big"


class InstructionNode(object):
    # TODO: it's not an instruction encoding descriptor. It should be in
    # another place.

    def __init__(self, opcode = None):
        self.opcode = opcode
        self.opc_dict = {}

        # unparsed yet
        self.instructions = []
        # already parsed one
        self.instruction = None

        self.count = 0
        self.instr_mnemonic = ""

    def dump(self):
        print("\nInsNode: " + str(self) + "[" + str(self.opcode) + "]")
        if self.count > 0:
            print(self.instructions[0].name)
            if self.count > 1:
                stderr.write("Warning: InstructionNode.count > 1 !")
        else:
            for key, node in self.opc_dict.iteritems():
                print("\n" + str(self) + " [" + str(key) + "] -> " + str(node))
                node.dump()


class InstrField(object):

    def __init__(self, length, val, num = 0):
        # TODO: according to `check`, `self.length == len(self.val)`. So, why
        # `length` arg is needed?
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


class Operand(InstrField):

    def __init__(self, length, name, num = 0):
        # TODO: arguments are same. Remove this?
        super(Operand, self).__init__(length, name, num)

    def __str__(self):
        return "Operand(" + str(self.length) + ', "' + self.val + '")'


class Opcode(InstrField):

    def __init__(self, length, val, num = 0):
        # TODO: "%%0%ub" % length % val
        # TODO: CINT meets it
        str_val = ("{0:0%ub}" % length).format(val)

        super(Opcode, self).__init__(length, str_val, num)

    def __str__(self):
        return "Opcode(" + str(self.length) + ", 0b" + self.val + ")"


class Reserved(InstrField):

    def __init__(self, length, val = 0, num = 0):
        # TODO: why InstrField.__init__'s val is not 0 by default?
        super(Reserved, self).__init__(length, str(val), num)

    def __str__(self):
        return ("Reserved(" + str(self.length) +
            ((", " + self.val) if self.val != "0" else "") + ")"
        )


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
        if isinstance(cur, InstrField):
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

    def set_comment(self, comment):
        # TODO: just assignment, is a method needed?
        self.comment = comment

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
            if isinstance(arg, InstrField):
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

    # TODO: make it a doc str
    # opcode is a list of tuples: [(val_1, len_1), ..., (val_k, len_k), ...]
    def get_full_opcode(self):
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


def find_common_opcode(instructions):
    """ Finds bit intervals occupied by opcodes in all instructions.

    :returns: list of tuples: [(off_1, len_1), ..., (off_k, len_k), ...]
    """
    # TODO: why "common" opcode? it can differ

    strs = [instr.string for instr in instructions]
    result = []
    cur_len = 0
    off = 0
    for i in range(min([len(string) for string in strs])):
        for x in strs:
            if x[i] not in "01":
                if cur_len > 0:
                    result.append((off, cur_len))
                    cur_len = 0
                break
        else:
            if cur_len == 0:
                off = i
            cur_len += 1
    # process tail
    if cur_len > 0:
        result.append((off, cur_len))
    return result


class InstructionSet(object):

    def __init__(self,
        name_to_format = {},
        instruction_list = [],
        endianess = "little",
        read_size = 1
    ):
        # TODO: some doc
        self.name_to_format = name_to_format
        self.instruction_list = instruction_list
        self.desc_bigendian = parse_endian(endianess)
        self.read_size = read_size
