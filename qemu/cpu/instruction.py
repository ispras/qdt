__all__ = [
#   InstructionField
        "Operand"
      , "Opcode"
      , "Reserved"
  , "re_disas_format"
  , "Instruction"
  , "InstructionTreeNode"
  , "build_instruction_tree"
  , "check_unreachable_instructions"
]

from .constants import (
    BYTE_BITSIZE,
)
from bisect import (
    insort,
)
from collections import (
    OrderedDict,
    defaultdict,
)
from common import (
    ee,
    lazy,
    intervalmap,
)
from copy import (
    deepcopy,
)
from six.moves import (
    zip_longest,
)
from re import (
    compile,
)
from six import (
    integer_types,
)


BUILD_INSTRUCTION_TREE_DEBUG = ee("QDT_BUILD_INSTRUCTION_TREE_DEBUG")
BUILD_INSTRUCTION_TREE_WARNINGS = ee("QDT_BUILD_INSTRUCTION_TREE_WARNINGS",
    "True"
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

    def __repr__(self):
        return type(self).__name__ + "(%u)" % self.bitsize


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

    def __repr__(self):
        return (
            type(self).__name__
          + '(%u, "%s", num = %u)' % (self.bitsize, self.name, self.num)
        )


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

    def __repr__(self):
        return (
            type(self).__name__
          + '(%u, val = "%s")' % (self.bitsize, self.val)
        )


class Reserved(InstructionField):
    pass


re_disas_format = compile("<((?:[a-zA-Z_]).*?)>|(.+?)")

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

        # mark for finding unreachable instructions
        self.used = False

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field(""); gen.pprint(self.mnemonic)
        for f in self.raw_fields:
            gen.gen_field(""); gen.pprint(f)
        for a in (
            "branch",
            "disas_format",
            "comment",
            "semantics",
            "priority",
        ):
            gen.gen_field(a + " = "); gen.pprint(getattr(self, a))
        gen.gen_end()

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

    def __call__(self, semantics):
        "Can be applied as a `@decorator` for semantics generation function"
        self.semantics = semantics
        if semantics.__doc__ is not None:
            self.comment = semantics.__doc__
        return semantics


class InstructionTreeNode(object):

    def __init__(self, interval = None):
        self.instruction = None
        self.interval = interval
        self.subtree = OrderedDict()
        self.default_opcodes = None
        self.reading_seq = []

    def __eq__(self, other):
        if self.instruction:
            return self.instruction == other.instruction
        else:
            if other.instruction:
                return False

        if self.interval != other.interval:
            return False

        for i, j in zip_longest(self.subtree.items(), other.subtree.items()):
            if i != j:
                return False

        return True

    def __ne__(self, other):
        return not self == other


class InfixSet(intervalmap):
    """ Multiple infixes joined in intervals.

Hints:
  - Calculate used infix intervals
    Initialize instance with one parameter and use method `add`
  - Calculate non-used infix intervals (for "default" case)
    Initialize instance with two parameters and use method `remove`

    """

    def __init__(self, interval_start, interval_end = None):
        super(InfixSet, self).__init__()
        if interval_end is None:
            interval_end = interval_start
        interval_end += 1
        self[interval_start:interval_end] = True

    def add(self, infix):
        self[infix:(infix + 1)] = True

    def remove(self, infix):
        self[infix:(infix + 1)] = None

    def iter_intervals(self):
        for (a, b), __ in self.items():
            b -= 1
            if a == b:
                yield (a,)
            else:
                yield (a, b)

    @property
    def intervals(self):
        return tuple(self.iter_intervals())

    def iter_lengths(self):
        for (a, b), __ in self.items():
            yield b - a

    @property
    def count(self):
        return sum(self.iter_lengths())

    def __lt__(self, other):
        if not isinstance(other, InfixSet):
            return NotImplemented

        if self.count < other.count:
            return True

        if self.count > other.count:
            return False

        if self.intervals < other.intervals:
            return True

        return False


def format_instructions(instructions, indent = "", max_bitsize = None):
    if max_bitsize is None:
        max_bitsize = max(i.bitsize for i in instructions)
    return "\n".join(
        "{0}{2:<{1}} (priority {3}) {4}".format(
            indent,
            max_bitsize,
            i.opcode_bits_string,
            i.priority,
            i.comment
        ) for i in instructions
    )


def print_instructions(instructions, indent = "", max_bitsize = None):
    print(
        format_instructions(
            instructions,
            indent = indent,
            max_bitsize = max_bitsize
        )
    )


def check_unreachable_instructions(instructions):
    unreachable_instructions = [i for i in instructions if not i.used]
    if unreachable_instructions:
        print("WARNING: some instructions unreachable (check instructions"
            " encoding or priority):"
        )
        print_instructions(unreachable_instructions, indent = "    ")


def common_bits_for_opcodes(instructions):
    "Finds bit numbers occupied by opcodes in all instructions."

    return instructions[0].opcode_bits.intersection(
        *[i.opcode_bits for i in instructions[1:]]
    )


def all_bits_for_opcodes(instructions):
    """ Returns bit numbers occupied by any opcode of at least one of the
    instructions.
    """

    return instructions[0].opcode_bits.union(
        *[i.opcode_bits for i in instructions[1:]]
    )


def all_bits_for_non_opcodes(instructions):
    """ Returns bit numbers occupied by any non-opcode field of at least one of
    the instructions.
    """

    return instructions[0].non_opcode_bits.union(
        *[i.non_opcode_bits for i in instructions[1:]]
    )


def all_opcode_boundaries(instructions):
    """ Returns bit numbers where opcode intervals start or end of at least one
    of the instructions.
    """

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
        infix = int(i.get_opcode_part(interval), base = 2)
        default_infixes = InfixSet(0, 2 ** interval[1] - 1)
        default_infixes.remove(infix)
        node.subtree[((infix,),)] = n = InstructionTreeNode()
        node.default_opcodes = default_infixes.intervals
        node = n
        # temporary info for reading sequence calculation
        node.limit_read = min_bitsize

    node.instruction = i
    i.used = True


def build_instruction_tree(node, instructions, read_bitsize,
    optimizations = True,
    checked_bits = set(),
    depth = 0 # for debugging purposes
):
    # Note, this is for formatting only.
    max_bitsize = max(i.bitsize for i in instructions)

    if BUILD_INSTRUCTION_TREE_DEBUG:
        print("DEBUG: Instructions (depth %d, count %d):" % (
            depth, len(instructions)
        ))
        print_instructions(instructions, max_bitsize = max_bitsize)

    if len(instructions) == 1:
        build_subtree_for_instruction(
            node, instructions[0], read_bitsize, checked_bits
        )
        return

    min_bitsize = min(i.bitsize for i in instructions)
    # temporary info for reading sequence calculation
    node.limit_read = min_bitsize

    # First approach: try to find distinguishable interval among the bits that
    # are opcodes for all instructions.

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
                if BUILD_INSTRUCTION_TREE_DEBUG:
                    print("First approach applied")
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
            ((opcode_bits & non_opcode_bits) - checked_bits) & min_bitsize_bits
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
                    if BUILD_INSTRUCTION_TREE_DEBUG:
                        print("Second approach applied")
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

            instructions_iter = iter(instructions)
            superset_i = next(instructions_iter)
            superset_b = superset_i.opcode_bits
            for i in instructions_iter:
                i_b = i.opcode_bits
                if superset_b <= i_b:
                    superset_i = i
                    superset_b = i_b
                elif not (i_b <= superset_b):
                    # not found instruction
                    break
            else:
                if BUILD_INSTRUCTION_TREE_DEBUG:
                    print("Third approach applied")
                build_subtree_for_instruction(
                    node, superset_i, read_bitsize, checked_bits
                )
                return

            # No instruction with superset opcode.

            # Fourth approach: select the instruction with the highest
            # `priority`.

            instructions = sorted(instructions,
                key = lambda i: i.priority,
                reverse = True
            )
            max_priority = instructions[0].priority

            if (    BUILD_INSTRUCTION_TREE_WARNINGS
                and sum(i.priority == max_priority for i in instructions) > 1
            ):
                print("WARNING: indistinguishable instructions - the first"
                    " instruction with the highest priority is used (check"
                    " instructions encoding or priority):"
                )
                print_instructions(instructions,
                    indent = "    ",
                    max_bitsize = max_bitsize
                )

            if BUILD_INSTRUCTION_TREE_DEBUG:
                print("Fourth approach applied")
            build_subtree_for_instruction(
                node, instructions[0], read_bitsize, checked_bits
            )
            return

    if BUILD_INSTRUCTION_TREE_DEBUG:
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
    all_infixes_count = 2 ** interval[1]

    # infix instruction distribution
    iid = defaultdict(list)
    for i in instructions:
        infix = i.get_opcode_part(interval)
        iid[infix].append(i)

    non_opcode_instructions = iid.pop(None, None)

    if non_opcode_instructions is not None:
        for __, infix_instructions in iid.items():
            infix_instructions.extend(non_opcode_instructions)

        # Notes:
        # 1. `default` is a "case" of `switch` block in C (used latter)
        # 2. it's an alphabetic and is sorted after all other infixes whose
        #    consist of digits only
        # 3. add `default` subtree only if not all possible infixes are used
        if len(iid) != all_infixes_count:
            iid["default"] = non_opcode_instructions

    # Note, subtree stores infixes:
    # binary string -> int
    # "default" -> None
    subtree = OrderedDict()
    checked_bits = checked_bits | integer_set(*interval)
    depth += 1
    for infix, infix_instructions in sorted(iid.items()):
        if infix != "default":
            infix = int(infix, base = 2)
        else:
            infix = None
        subtree[infix] = n = InstructionTreeNode()
        build_instruction_tree(n, infix_instructions,
            read_bitsize,
            optimizations = optimizations,
            checked_bits = checked_bits,
            depth = depth
        )

    if not optimizations:
        # Note, only infix order is matter now. Instructions with same infix
        # were sorted by the corresponding next common infix during recursive
        # `build_instruction_tree` call.
        default_subtree_node = subtree.pop(None, None)
        default_opcodes = InfixSet(0, all_infixes_count - 1)

        for infix, subtree_node in subtree.items():
            node.subtree[((infix,),)] = subtree_node
            default_opcodes.remove(infix)

        if default_subtree_node is not None:
            node.subtree[None] = default_subtree_node

        node.default_opcodes = default_opcodes.intervals

        return

    optimize_instruction_subtree(node, subtree)


def optimize_instruction_subtree(node, subtree):
    """ The current algorithm, which propagates non-opcode instructions to all
    subtrees, may result in some subtrees being the same. To reduce the size of
    the tree, same subtrees are removed by combining infixes.
    """

    merged_subtree = []
    bitsize = node.interval[1]
    all_infixes_count = 2 ** bitsize
    default_subtree_node = subtree.pop(None, None)
    default_infixes = InfixSet(0, all_infixes_count - 1)

    for infix, subtree_node in subtree.items():
        if (    default_subtree_node is not None
            and subtree_node == default_subtree_node
        ):
            continue

        default_infixes.remove(infix)

        for infixes, merged_subtree_node in merged_subtree:
            if merged_subtree_node == subtree_node:
                infixes.add(infix)
                break
        else:
            merged_subtree.append((InfixSet(infix), subtree_node))

    # maximum count of subtree infixes
    max_csi = 0
    default_candidate_index = -1
    used_infixes_count = 0

    for i, (infixes, subtree_node) in enumerate(merged_subtree):
        csi = infixes.count
        used_infixes_count += csi
        if csi >= max_csi:
            max_csi = csi
            default_candidate_index = i

    if default_subtree_node is not None:
        # All subtrees match the default subtree.
        if len(merged_subtree) == 0:
            node.instruction = default_subtree_node.instruction
            node.interval = default_subtree_node.interval
            node.subtree = default_subtree_node.subtree
            node.default_opcodes = default_subtree_node.default_opcodes
            return

        # If the "default" case is present then it will be used for the subtree
        # with the largest count of infixes (if the count is the same then with
        # the largest first infix) to make it easier to identify the same
        # subtrees.

        default_candidate_infixes, default_candidate = (
            merged_subtree[default_candidate_index]
        )

        if default_infixes < default_candidate_infixes:
            merged_subtree.pop(default_candidate_index)
            insort(merged_subtree, (default_infixes, default_subtree_node))
            default_subtree_node = default_candidate
            default_infixes = default_candidate_infixes
    else:
        subtree_node_infixes, subtree_node = merged_subtree[0]
        if (    len(merged_subtree) == 1
            and subtree_node_infixes.count == all_infixes_count
        ):
            node.instruction = subtree_node.instruction
            node.interval = subtree_node.interval
            node.subtree = subtree_node.subtree
            node.default_opcodes = subtree_node.default_opcodes
            return

        # If the "default" case is not present but all possible infixes are
        # used then the "default" case will be used for the subtree with the
        # largest count of infixes (if the count is the same then with the
        # largest first infix) to make it easier to identify the same subtrees.

        if used_infixes_count == all_infixes_count:
            default_infixes, default_subtree_node = (
                merged_subtree.pop(default_candidate_index)
            )

    for infixes, merged_subtree_node in merged_subtree:
        node.subtree[infixes.intervals] = merged_subtree_node

    if default_subtree_node is not None:
        node.subtree[None] = default_subtree_node

    node.default_opcodes = default_infixes.intervals
