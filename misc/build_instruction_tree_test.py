from collections import (
    namedtuple,
)
from qemu import (
    BYTE_BITSIZE,
    SUPPORTED_READ_BITSIZES,
    Operand,
    Opcode,
    Instruction,
    InstructionTreeNode,
    build_instruction_tree,
    check_unreachable_instructions,
)
from random import (
    randint,
)


def example_hypothesis(non_opt_tree, opt_tree, instructions):
    """ User-defined boolean function that tests a certain hypothesis based on
    the resulting trees and the list of instructions.

    Example:
        def check_hypothesis_recursive(node):
            if node.instruction is not None:
                return False
            else:
                for infix, subtree in node.subtree.items():
                    if isinstance(infix, tuple) and len(infix) > 1:
                        return True
                    s = check_hypothesis_recursive(subtree)
                    if s:
                        return True
                return False

        return check_hypothesis_recursive(opt_tree)

    Another example:
        non_opt_tree_stats = compute_stats(non_opt_tree, instructions)
        opt_tree_stats = compute_stats(opt_tree, instructions)

        return opt_tree_stats.aver_depth < non_opt_tree_stats.aver_depth
    """

    return True


TreeStats = namedtuple(
    "TreeStats",
    "unreachable leaves min_depth aver_depth max_depth"
)


def traverse_tree(node, depths, used_instructions, depth = 0):
    if node.instruction is not None:
        used_instructions.append(node.instruction)
        depths.append(depth)
    else:
        for _, subtree in node.subtree.items():
            traverse_tree(subtree, depths, used_instructions, depth + 1)


def compute_stats(node, instructions):
    depths = []
    used_instructions = []
    traverse_tree(node, depths, used_instructions)
    return TreeStats(
        unreachable = len(set(instructions) - set(used_instructions)),
        leaves = len(used_instructions),
        min_depth = min(depths),
        aver_depth = sum(depths) / float(len(depths)),
        max_depth = max(depths)
    )


def print_stats(node, instructions, msg):
    tree_stats = compute_stats(node, instructions)
    print("""\
STATS ({msg}):
Instructions count: {instructions}
Unreachable instructions count: {unreachable}
Leaves count: {leaves}
Min-Average-Max depth: {min_d} - {aver_d:.2f} - {max_d}""".format(
    msg = msg,
    instructions = len(instructions),
    unreachable = tree_stats.unreachable,
    leaves = tree_stats.leaves,
    min_d = tree_stats.min_depth,
    aver_d = tree_stats.aver_depth,
    max_d = tree_stats.max_depth
        )
    )


def print_tree(node, offset = ""):
    if node.instruction is not None:
        print("{0}{1}".format(offset, node.instruction.name))
    else:
        print("{0}[{1} {2}]:".format(offset, *node.interval))
        for opcode, subtree in node.subtree.items():
            print("{0}{1}:".format(offset, opcode))
            print_tree(subtree, offset + "    ")


def process_fixed_instructions(fixed_instructions, *a, **kw):
    raw_instructions = [
        i if (type(i) is tuple) else (i, 0) for i in fixed_instructions
    ]
    return process_instructions(raw_instructions, *a, **kw)


def process_random_instructions(min_ins_size, max_ins_size, ins_count,
    *a, **kw
):
    kw = dict(kw)
    kw["print_only_true"] = True

    checked_sets = 0
    while True:
        raw_instructions = list(
            gen_raw_instructions(min_ins_size, max_ins_size, ins_count)
        )
        if process_instructions(raw_instructions, *a, **kw):
            break
        else:
            checked_sets += 1
            if checked_sets % 100 == 0:
                print("Checked sets: %d" % checked_sets)


def gen_raw_instructions(min_ins_size, max_ins_size, ins_count):
    "sizes are in bytes"

    ins_strings = set()
    while len(ins_strings) < ins_count:
        ins_len = randint(min_ins_size, max_ins_size) * BYTE_BITSIZE
        ins = ""
        for __ in range(ins_len):
            ins += "01x"[randint(0, 2)]
        if ins not in ins_strings:
            ins_strings.add(ins)
            yield ins, randint(0, ins_count - 1)


def process_instructions(raw_instructions, read_size,
    check_hypothesis = example_hypothesis,
    print_only_true = False,
):
    read_bitsize = read_size * BYTE_BITSIZE

    if read_bitsize not in SUPPORTED_READ_BITSIZES:
        raise RuntimeError(
            "Valid `read_size` values are %s bytes" % (", ".join(
                i // BYTE_BITSIZE for i in SUPPORTED_READ_BITSIZES
            ))
        )

    instructions = []
    for i, (ins_str, ins_priority) in enumerate(raw_instructions):
        fields = []
        op_count = 0
        for c in ins_str:
            if c == 'x':
                fields.append(Operand(1, "o" + str(op_count)))
                op_count += 1
            else:
                fields.append(Opcode(1, int(c)))
        ins = Instruction("i" + str(i), *fields, priority = ins_priority)
        ins.name = ins.mnemonic
        ins.read_bitsize = read_bitsize
        instructions.append(ins)

    try:
        non_opt_tree = InstructionTreeNode()
        build_instruction_tree(non_opt_tree, instructions, read_bitsize,
            optimizations = False
        )
        opt_tree = InstructionTreeNode()
        build_instruction_tree(opt_tree, instructions, read_bitsize,
            optimizations = True
        )
    except RuntimeError:
        print("Instructions set resulting in excepton: %s" % raw_instructions)
        raise

    res = check_hypothesis(non_opt_tree, opt_tree, instructions)

    if not print_only_true or res:
        print("Instructions set: %s" % raw_instructions)
        print("Tree without optimizations:")
        print_tree(non_opt_tree)
        print("Tree with optimizations:")
        print_tree(opt_tree)
        print_stats(non_opt_tree, instructions, "without optimizations")
        print_stats(opt_tree, instructions, "with optimizations")
        check_unreachable_instructions(instructions)

        print("Hypothesis result: %r" % (res,))

    return res


def main():
    print("Fixed instructions")
    for raw_instructions, read_size, check_hypothesis in (
        # There you can specify a `list` of fixed instructions.
        # Each instruction must be aligned by the read_size.
        # Each instruction is written as a tuple of a unique bit-string and
        # an integer priority or as a unique bit-string (with priority 0
        # by default).
        # There are some examples below.

        (
            [
                "1010xxxx",
               ("0101xx00xxxx1100", 2),
            ],
            1, # read_size
            example_hypothesis,
        ),

        # See "i1" instruction in tree.
        # All subtrees are the same with the "default" subtree.
        (
            [
                "111xxx1x",
               ("x1xx01xx", 1),
            ],
            1,
            example_hypothesis,
        ),

        # See "i2" instruction in tree.
        # No "default" case; all infixes used; all subtrees are the same.
        (
            [
                "1xx1xx11",
                "x10100x0",
               ("x101xx1x", 1),
            ],
            1,
            example_hypothesis,
        ),

        # See "i1" and "i2" instructions in tree.
        # "default" case reassignment helps identify same subtrees.
        (
            [
               ('1xx101xx', 1),
               ('10xxx1xx', 2),
                '1xx1xx10',
               ('xx001111', 1),
            ],
            1,
            example_hypothesis,
        ),

        # See "i2" and "i3" instructions in tree.
        # Some subtrees are the same but different from the "default" subtree.
        (
            [
                'xxxx0111',
                'xx1xx100',
               ('1x1101xx', 1),
               ('xxxxx1xx', 2),
            ],
            1,
            example_hypothesis,
        ),
    ):
        print("\n")

        process_fixed_instructions(raw_instructions, read_size,
            check_hypothesis = check_hypothesis
        )

    print("\n\nRandom instructions\n")

    process_random_instructions(
        min_ins_size = 1,
        max_ins_size = 2,
        ins_count = 5,
        read_size = 1
    )


if __name__ == "__main__":
    main()
