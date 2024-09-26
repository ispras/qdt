from common import (
    CodeWriter,
    DictStack,
)
from common.pygen import (
    dumps,
)
from qemu import (
    DefineFinder,
    Instruction,
    NodeVisitor,
    Operand,
    Short,
    ShortStatement,
    VersatileIdentifier,
)
from source import (
    BinaryOperator,
    BlockParser,
    BodyTree,
    BranchElse,
    BranchIf,
    Comment,
    CBlock,
    CDecl,
    check_cols_fix_up,
    CSTR,
    Function,
    Late,
    LateLinker,
    VarUsageAnalyzer,
)
# for exec
import qemu
import source

from argparse import (
    ArgumentParser,
)
from collections import (
    defaultdict,
)
from copy import (
    deepcopy,
)
from difflib import (
    unified_diff
)
from traceback import (
    format_exc,
)

# Specification operator (:=) can set instruction attributes.
instruction_attributes = dict(
    branch = bool,
    disas_format = str,
    # some attributes cannot be set using := operator
    # "comment",
    # "semantics,
    mnemonic = str,
    priority = int,
)


def check_dump(insn):
    code = dumps(insn)
    locals_ = {}
    globals_ = dict(globals())
    globals_.update(qemu.__dict__)
    globals_.update(source.__dict__)
    try:
        exec(code, globals_, locals_)
    except:
        print(code)
        raise
    for loaded in locals_.values():
        if isinstance(loaded, Instruction):
            break
    else:
        raise AssertionError(
            "code does not provide Instruction object\n%s" % code
        )
    loaded_code = dumps(loaded)
    if code != loaded_code:
        diff = "\n".join(
            unified_diff(code.split("\n"),
            loaded_code.split("\n"))
        )
        raise AssertionError(
            "dumps/loads-ed instruction differs\n%s\ndiff:\n%s" % (
                loaded_code, diff
            )
        )


def print_layout(insn):
    print("%s.bitsize == %d" % (insn.mnemonic, insn.bitsize))
    offset = 0
    for f in insn.fields:
        print("\t%2d %2d %s" % (
            offset,
            f.bitsize,
            f.name if isinstance(f, Operand) else f.val,
        ))
        offset += f.bitsize


def handle_insn(insn,
    print_disas_format = False,
    print_semantics = False,
):
    print("\n\n")
    check_dump(insn)
    print_layout(insn)
    if print_disas_format:
        print("disas_format: %r" % insn.disas_format)
    if print_semantics:
        print("semantics {\n%s}\n" % str_as_function_body(insn.semantics))


def str_as_function_body(stmnts):
    sem = deepcopy(stmnts)

    LateLinker(sem).visit()

    body = BodyTree(children = sem)

    VarUsageAnalyzer(body).visit()

    cw = CodeWriter()
    cw.add_lang("c", "    ")
    cw.add_lang("cpp", "  ", "#")
    cw.add_lang("late", "    ")
    cw.new_line = True

    with cw.c:
        body.__c__(cw)

    return check_cols_fix_up(cw.w.getvalue())


class VID2Late(NodeVisitor):

    def __visit__(self, cur):
        if isinstance(cur, VersatileIdentifier):
            self.replace(Late(cur.name))


class NamedList(list):

    def __init__(self, list_name = "list"):
        super(NamedList, self).__init__()
        self.list_name = list_name

    def __pygen_pass__(self, g):
        instructions = list(self)
        yield instructions, True
        g.write(self.list_name + " = ")
        g.pprint(instructions)


def analyze_instruction_block(heading):
    heading.insn = None

    l = str(heading)
    # remove comments from top block lines
    l = l.split("#")[0]

    if not l:
        return

    try:
        insn = Short.parse(l)
    except:
        # before debug call stack another exception
        insn_msg = format_exc()
        insn = None

    try:
        decl = CDecl.parse(l)
    except:
        func_msg = format_exc()
        decl = None

    if (insn or decl) is None:
        for msg, parser in (
            (insn_msg, Short),
            (func_msg, CDecl),
        ):
            print("parser: " + str(parser))
            try:
                parser.parse(l, debug = True)
            except:
                pass
            # after parser log printed
            print(msg)

        raise SyntaxError("%d: bad block (all parsers failed)" % (heading.n,))

    heading.insn = insn
    heading.decl = decl


def find_instruction_specifiers(heading):
    heading.specs = specs = defaultdict(list)

    insn = heading.insn

    if insn is None:
        return

    op_names = set(f.name for f in insn.raw_fields if isinstance(f, Operand))

    stack = [heading]

    while stack:
        line = stack.pop()
        block = line.child

        if not block:
            continue

        for sline in block:
            no_specs = True
            for d in find_defines(sline.stmnts):
                lvalue = d.name
                if not isinstance(lvalue, VersatileIdentifier):
                    raise SyntaxError(
                        "%d: lvalue of `:=` must be an ID, not %r"
                        % (sline.n, lvalue)
                    )
                op_name = lvalue.name

                if op_name in op_names:
                    rvalue = d.value
                    if not isinstance(rvalue, CSTR):
                        raise SyntaxError(
                '%d: instruction operand replacement (rvalue of `:=`) must be'
                ' a "C-string", not %r'
                            % (heading.n, rvalue)
                        )

                    specs[op_name].append(str(rvalue))
                    # Do not go deeper right now.
                    # Some definitions can be for choisen instruction variants.
                    # They will be handled later during recursive
                    #     `iter_multiply_instruction_blocks` calls.
                    no_specs = False
                elif op_name in instruction_attributes:
                    pass

            if no_specs:
                stack.append(sline)


def find_defines(stmnts):
    return DefineFinder(stmnts).visit().defines


_c2py_op = {
    "&&" : "and",
    "||" : "or",
    # Inside expressions, define operator returns True if right value equals
    # to currently defined value.
    ":=" : "==",
}.get

c2py_op = lambda op : _c2py_op(op, op)


class Evaluator(NodeVisitor):

    def __init__(self, root, ns = {}, **kw):
        super(Evaluator, self).__init__(root, **kw)
        self.ns = DictStack(backing = ns)

    def __getitem__(self, o):
        return self.ns["_evaluated_%d" % id(o)]

    def __setitem__(self, o, v):
        self.ns["_evaluated_%d" % id(o)] = v

    def __leave__(self, o):
        if isinstance(o, CSTR):
            evaluated = str(o)
        elif isinstance(o, VersatileIdentifier):
            evaluated = self.ns[o.name]
        elif isinstance(o, BinaryOperator):
            code = "_evaluated_%d %s _evaluated_%d" % (
                id(o.children[0]),
                c2py_op(o.op_str),
                id(o.children[1]),
            )
            evaluated = eval(code, self.ns)
        else:
            return

        self[o] = evaluated


def eval_def_rvalue(rvalue, ns = {}):
    evaluator = Evaluator([rvalue], ns = ns)
    evaluator.visit()
    val = evaluator[rvalue]
    return val


def iter_block_lines_specified(op_name, op_val, block):
    for line in block:
        for d in find_defines(line.stmnts):
            # find_instruction_specifiers missed it
            assert isinstance(d.name, VersatileIdentifier)

            l_op_name = d.name.name

            if l_op_name == op_name:
                # find_instruction_specifiers missed it
                assert isinstance(d.value, CSTR)

                l_op_val = str(d.value)

                if l_op_val == op_val:

                    prefix_line = type(line)()
                    prefix_line.stmnts = []
                    yield prefix_line

                    if line.child:
                        for sline in iter_block_lines_specified(
                            op_name, op_val, line.child
                        ):
                            yield sline

                break
        else:
            if line.child:
                specified_line = type(line)()
                specified_line.stmnts = line.stmnts

                specified_line.child = type(line.child)(
                    iter_block_lines_specified(
                         op_name, op_val, line.child
                    )
                )
            else:
                specified_line = line

            yield specified_line


def iter_multiply_instruction_blocks(heading):
    # Note: during recursion, after specify_instruction_operand:
    # - Possibly, there are operand specifications those are actual for
    #   this specified instruction (variant) only.
    # - Substitution might add more operands that could be specified.
    #   So, more `name := value` pairs could be distinguished as
    #   specifications.
    find_instruction_specifiers(heading)

    specs = heading.specs
    if not specs:
        yield heading
        return

    op_name = sorted(specs)[0]
    op_vals = specs.pop(op_name)

    # don't deepcopy of parent
    heading.parent = None

    for op_val in op_vals:
        specified = deepcopy(heading)

        block = specified.child

        # TODO: it might be not so simple
        block[:] = iter_block_lines_specified(op_name, op_val, block)

        insn = specified.insn

        specify_instruction_operand(insn, op_name, op_val)

        for subspec in iter_multiply_instruction_blocks(specified):
            yield subspec


def specify_instruction_operand(insn, op_name, op_val):
    # find place to substitute
    for field_i, f in enumerate(insn.raw_fields):
        if not isinstance(f, Operand):
            continue
        if f.name == op_name:
            break
    else:
        raise ValueError(
            "No place for opcode '%s' defined" % op_name
        )

    l = eval(op_val)
    try:
        sub_insn = Short.parse(l)
    except:
        # before debug call stack another exception
        msg = format_exc()
        try:
            Short.parse(l, debug = True)
        except:
            pass
        # after parser log printed
        print(msg)
        raise

    if isinstance(sub_insn, Instruction):
        insn.mnemonic = sub_insn.mnemonic
        sub_raw_fields = sub_insn.raw_fields
    else:
        sub_raw_fields = sub_insn

    sub_raw_fields_size = sum(f.bitsize for f in sub_raw_fields)
    assert sub_raw_fields_size == f.bitsize

    raw_fields = list(insn.raw_fields)
    raw_fields[field_i:(field_i + 1)] = sub_raw_fields
    insn.raw_fields = tuple(raw_fields)


def set_attributes(heading):
    attrs = dict()
    base_ns = DictStack(attrs)

    insn = heading.insn

    base_ns.update(
        (a, getattr(insn, a)) for a in instruction_attributes
    )

    stack = [(heading, base_ns)]

    while stack:
        line, ns = stack.pop()
        block = line.child

        if not block:
            continue

        for sline in block:
            stack.append((sline, ns.push()))

            for d in find_defines(sline.stmnts):
                # find_instruction_specifiers missed it
                assert isinstance(d.name, VersatileIdentifier)

                def_name = d.name.name

                op_val = eval_def_rvalue(d.value, ns)

                ns[def_name] = op_val
                if def_name in instruction_attributes:
                    attrs[def_name] = op_val

    block = heading.child

    for attr, val_str in attrs.items():
        val = eval(val_str)
        setattr(insn, attr, instruction_attributes[attr](val))

    block[:] = iter_block_lines_without_defines(block)


def iter_block_lines_without_defines(block):
    for line in block:
        for __ in find_defines(line.stmnts):
            # replace line with its block or just drop (if without block)
            if line.child:
                for sline in iter_block_lines_without_defines(
                    line.child
                ):
                    yield sline

            break
        else:
            if line.child:
                line.child[:] = iter_block_lines_without_defines(
                    line.child
                )
            yield line


def parse_lines(heading):
    block = heading.child

    if block is None:
        return

    for line in block:
        # strip comment
        parts = str(line).split("#", 1)
        code = parts[0].strip()
        if len(parts) > 1:
            comment = parts[1].strip()
            stmnts = [Comment(comment)]
        else:
            stmnts = []

        # Don't try to parse `Short` instruction encoding.
        if code and heading.parent is not None:
            try:
                stmnt = ShortStatement.parse(code)
            except:
                # before debug call stack another exception
                msg = format_exc()
                print("code: " + code)
                try:
                    ShortStatement.parse(code, debug = True)
                except:
                    pass
                # after parser log printed
                print(msg)
                raise
            else:
                stmnts.append(stmnt)

        line.stmnts = stmnts

        parse_lines(line)


def merge_statements(heading):
    block = heading.child
    if block is not None:
        sub_stmnts = []
        for line in block:
            merge_statements(line)
            sub_stmnts.extend(line.stmnts)

        sub_stmnts = list(iter_join_BranchElse(sub_stmnts))

        if sub_stmnts:
            stmnts = heading.stmnts
            if stmnts:
                last_stmnt = stmnts[-1]
                if not isinstance(last_stmnt, CBlock):
                    stmnts[-1] = last_stmnt = BranchIf(last_stmnt)
                last_stmnt(*sub_stmnts)
            else:
                stmnts[:] = sub_stmnts


def iter_join_BranchElse(stmnts):
    prev_stmnt = None
    for stmnt in stmnts:

        if isinstance(stmnt, BranchElse):
            if not isinstance(prev_stmnt, BranchIf):
                raise SyntaxError("%r must follows be BranchIf, not %r" % (
                    stmnt, prev_stmnt
                ))
            prev_stmnt(stmnt)
            continue

        yield stmnt

        prev_stmnt = stmnt


def main():
    ap = ArgumentParser(
        description = """\
Converts short form instructions definitions to script defines them.
"""     ,
    )
    arg = ap.add_argument

    arg("short_desc_file_name")
    arg("-r", "--read-bitsize",
        default = 32,
        type = int,
    )
    arg("-o", "--output-file-name")
    arg("-n", "--list-name",
        default = "instructions",
        type = str,
        help = "name of list of instructions",
    )
    arg("-t", "--types-list-name",
        default = "types",
        type = str,
        help = "name of list of types",
    )
    arg("-s", "--print-semantics",
        action = "store_true",
    )
    arg("-d", "--print-disas-format",
        action = "store_true",
    )

    args = ap.parse_args()
    read_bitsize = args.read_bitsize
    output_file_name = args.output_file_name

    with open(args.short_desc_file_name, "r") as f:
        short_desc = f.read()

    bp = BlockParser()
    top = bp.parse(short_desc)

    # analyze instructions

    parse_lines(top)

    insn_lines = []
    decl_lines = []

    for top_line in top.child:
        analyze_instruction_block(top_line)

        insn = top_line.insn
        if insn is not None:
            insn.read_bitsize = read_bitsize
            insn_lines.extend(iter_multiply_instruction_blocks(top_line))

        decl = top_line.decl
        if decl is not None:
            decl_lines.append(top_line)

    # Handle declarations

    types = NamedList(
        list_name = args.types_list_name
    )

    for heading in decl_lines:
        t = heading.decl

        if isinstance(t, Function):
            merge_statements(heading)
            VID2Late(heading.stmnts).visit()
            t.body = BodyTree(children = heading.stmnts)

        types.append(t)

    # handle instructions

    insts = NamedList(
        list_name = args.list_name,
    )

    for heading in insn_lines:
        i = heading.insn

        set_attributes(heading)

        if i.mnemonic == "skip":
            continue

        merge_statements(heading)
        VID2Late(heading.stmnts).visit()

        i.semantics = heading.stmnts

        handle_insn(i,
            print_disas_format = args.print_disas_format,
            print_semantics = args.print_semantics,
        )
        insts.append(i)

    if args.print_semantics:
        for t in types:
            if isinstance(t, Function):
                # Note: can't use regular chunks mechanism until fully linked.
                print("%s %s(%s)\n{\n%s}\n" % (
                    t.ret_type.name,
                    t.c_name,
                    ", ".join((a.type.name + " " + a.name) for a in t.args),
                    str_as_function_body(t.body.children),
                ))

    if output_file_name:
        insts_text = dumps(insts)
        types_text = dumps(types)
        with open(output_file_name, "w") as f:
            f.write("# this file is generated by " + ap.prog + "\n")
            f.write("from qemu import *\n")
            f.write("from source import *\n")
            f.write("\n")
            f.write(insts_text + "\n")

            # TODO
            if False and types:
                f.write("\n")
                f.write(types_text + "\n")

if __name__ == "__main__":
    exit(main() or 0)
