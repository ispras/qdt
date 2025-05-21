from common import (
    CodeWriter,
    DictStack,
    OrderedSet,
)
from common.pygen import (
    dumps,
)
from qemu import (
    DefineFinder,
    Instruction,
    NodeVisitor,
    Opcode,
    Operand,
    operand_num,
    operand_num_from_bitoffset,
    operand_num_to_bitoffset,
    Reserved,
    separate_instructions,
    Short,
    ShortStatement,
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
    CINT,
    CSTR,
    Function,
    gen_init_string,
    Late,
    LateLinker,
    LoopFor,
    Variable,
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
from itertools import (
    chain,
)
from traceback import (
    format_exc,
)


def strip_comments(heading):
    try:
        i = heading.index("#")
    except ValueError:
        pass
    else:
        comment = heading[i + 1:]
        del heading[i:]
        heading.comment = comment

    child = heading.child
    if child is None:
        return
    for line in child:
        strip_comments(line)


def iter_comments(heading):
    comment = heading.comment
    if comment is not None:
        yield comment
    if not heading.multiline:
        return
    for line in heading.child:
        for sub_comment in iter_comments(line):
            yield sub_comment


iter_comment = lambda heading: chain(*iter_comments(heading))


class Cline(BlockParser.Line):
    multiline = False
    comment = None
    stmnts = ()

    strip_comments = strip_comments
    iter_comments = iter_comments
    iter_comment = iter_comment

    @property
    def root(self):
        return self.child[-1] if self.multiline else self


class CBlockParser(BlockParser):
    Line = Cline


# Specification operator (:=) can set instruction attributes.
instruction_attributes = dict(
    branch = bool,
    disas_format = str,
    comment = str,
    # some attributes cannot be set using := operator
    # "semantics,
    mnemonic = str,
    priority = int,
    encoding = str,
)


dump_insn = lambda insn: dumps(insn, imports = False)


def check_dump(insn):
    code = dump_insn(insn)
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
    loaded_code = dump_insn(loaded)
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
    try:
        bitsize = insn.bitsize
    except:
        bitsize = "[exception]"
    print("%s.bitsize == %s" % (insn.mnemonic, bitsize))
    try:
        fields = insn.fields
    except:
        print("[exception during fields printing]")
        return
    name2ops = operand_num_to_bitoffset(fields)
    offset = 0
    try:
        for f in fields:
            if isinstance(f, Operand):
                if len(name2ops[f.name]) > 1:
                    pretty = f.name + "[%d:%d]" % (
                        f.num + f.bitsize - 1, f.num
                    )
                else:
                    pretty = f.name
            else:
                pretty = f.val
            print("\t%2d %2d %s" % (
                offset,
                f.bitsize,
                pretty,
            ))
            offset += f.bitsize
    finally:
        operand_num_from_bitoffset(fields)


def print_function(t):
    try:
        print("%s %s(%s)\n{\n%s}\n" % (
            t.ret_type.name,
            t.c_name,
            ", ".join(
                    check_cols_fix_up(a.declaration_string)
                        for a in t.args
                ) if t.args is not None else "void",
            str_as_function_body(t.body.children),
        ))
    except:
        # Sometimes, likely because of Late, a C code cannot be generated.
        print("%s: function stringification failed:\n%s" % (
            t.c_name, format_exc()
        ))


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
        try:
            sem = str_as_function_body(insn.semantics)
        except:
            # Sometimes, likely because of Late, a C code cannot be generated.
            print("semantics stringification failed:\n" + format_exc())
        else:
            print("semantics {\n%s}\n" % sem)


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


class NamedList(list):

    def __init__(self, list_name = "list"):
        super(NamedList, self).__init__()
        self.list_name = list_name

    def __pygen_pass__(self, g):
        instructions = list(self)
        yield instructions, True
        g.write(self.list_name + " = ")
        g.pprint(instructions)


# Note, `int i` is a valid `Short` instruction encoding.
# I.e. mnemonic = "int", bit lenght = 1 bit, i is an operand.
# So, first try to parse line as C declaration.
line_parsers = [
    ("decls", CDecl),
    ("insn", Short),
]


def analyze_instruction_block(heading):
    heading.insn = None

    l = str(heading)

    if not l:
        return

    errors = []

    for target, parser in line_parsers:
        try:
            val, multiline = parse_multiline(parser, heading)
            if val is None:
                # Sometimes `SyntaxError` results in None return instead of
                # exception raising,
                errors.append(("[parser returned None]", parser))
        except SyntaxError:
            msg = format_exc()
            errors.append((msg, parser))
            setattr(heading, target, None)
        else:
            setattr(heading, target, val)
            if multiline:
                heading.multiline = True
            # try until first success
            break

    if len(errors) == len(line_parsers):
        for msg, parser in errors:
            print("parser: " + str(parser))
            try:
                parse_multiline(parser, heading, debug = True)
            except:
                pass
            # after parser log printed
            print(msg)

        raise SyntaxError("%d: %r: bad line (all parsers failed)" % (
            heading.n, str(heading)
        ))


def find_instruction_specifiers(heading):
    heading.specs = specs = defaultdict(OrderedSet)

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
                if not isinstance(lvalue, Late):
                    raise SyntaxError(
                        "%d: %r: lvalue of `:=` must be an ID, not %r"
                        % (sline.n, str(sline), lvalue)
                    )
                op_name = lvalue.name

                if op_name in op_names:
                    rvalue = d.value
                    if not isinstance(rvalue, CSTR):
                        raise SyntaxError(
        '%d: %r: instruction operand replacement (rvalue of `:=`) must be'
        ' a "C-string", not %r'
                            % (heading.n, str(heading), rvalue)
                        )

                    specs[op_name].add(str(rvalue))
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
        if isinstance(o, (CSTR, CINT)):
            evaluated = o.v
        elif isinstance(o, Late):
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


def iter_block_lines_specified(op_name, op_val, block, new_block):
    for line in block:
        for d in find_defines(line.stmnts):
            # find_instruction_specifiers missed it
            assert isinstance(d.name, Late)

            l_op_name = d.name.name

            if l_op_name != op_name:
                continue

            # find_instruction_specifiers missed it
            assert isinstance(d.value, CSTR)

            l_op_val = str(d.value)

            if l_op_val == op_val:

                prefix_line = type(line)()
                prefix_line.parent = new_block
                prefix_line.n = line.n
                # TODO: is content to be copied?

                yield prefix_line

                if line.child:
                    for sline in iter_block_lines_specified(
                        op_name, op_val, line.child, new_block
                    ):
                        yield sline

            break
        else:
            specified_line = type(line)()
            if line.stmnts:
                specified_line.stmnts = deepcopy(line.stmnts)
            specified_line.n = line.n
            specified_line.parent = new_block
            # TODO: is content to be copied?

            if line.child:
                specified_line.child = sblock = type(line.child)()
                sblock.heading = specified_line
                sblock[:] = iter_block_lines_specified(
                    op_name, op_val, line.child, sblock
                )

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

    if len(op_vals) == 1:
        # can change heading inplace
        op_val = next(iter(op_vals))
        block = heading.child
        block[:] = iter_block_lines_specified(op_name, op_val, block, block)
        specify_instruction_operand(heading.insn, op_name, op_val)
        for subspec in iter_multiply_instruction_blocks(heading):
            yield subspec
        return

    # don't deepcopy of parent
    heading.parent = None

    # Don't deepcopy child block.
    # It will be rebuilt by `iter_block_lines_specified`.
    block = heading.child
    heading.child = None

    for op_val in op_vals:
        specified = deepcopy(heading)

        sblock = type(block)()
        sblock.heading = specified
        specified.child = sblock
        sblock[:] = iter_block_lines_specified(op_name, op_val, block, sblock)

        insn = specified.insn

        specify_instruction_operand(insn, op_name, op_val)

        for subspec in iter_multiply_instruction_blocks(specified):
            yield subspec

    # revert it back
    heading.child = block


def specify_instruction_operand(insn, op_name, op_val):
    # find place to substitute
    op_parts = []
    for f in insn.raw_fields:
        if not isinstance(f, Operand):
            continue
        if f.name == op_name:
            op_parts.append(f)

    if not op_parts:
        raise ValueError(
            "No place for opcode '%s' defined" % op_name
        )

    l = op_val
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

    prev_field_size = sum(f.bitsize for f in op_parts)
    sub_raw_fields_size = sum(f.bitsize for f in sub_raw_fields)

    if sub_raw_fields_size != prev_field_size:
        raise ValueError(
            "%s: %d-bit instruction field is replaced with field(s)"
            " of different length %d bit(s): %r" % (
                op_name, prev_field_size, sub_raw_fields_size, l
            )
        )

    sub_raw_fields = list(sub_raw_fields)
    op_parts.sort(key = operand_num)

    replacements = {}

    for f in op_parts:
        replacement = []
        replacements[f] = replacement
        rest = f.bitsize
        while rest:
            r = sub_raw_fields.pop()
            if rest < r.bitsize:
                left_size = r.bitsize - rest
                if isinstance(r, Opcode):
                    split_i = left_size
                    sub_raw_fields.append(Opcode(left_size, r.val[:split_i]))
                    r.val = r.val[split_i:]
                elif isinstance(r, Operand):
                    sub_raw_fields.append(
                        Operand(left_size, r.name, num = r.num)
                    )
                    # compensate operand split
                    for rr in sub_raw_fields:
                        if isinstance(rr, Operand) and rr.name == r.name:
                            rr.num += 1
                elif isinstance(r, Reserved):
                    sub_raw_fields.append(type(r)(left_size))
                else:
                    raise ValueError("Wrong field type %s" % type(f))
                r.bitsize = rest
            replacement.append(r)
            rest -= r.bitsize

    raw_fields = list(insn.raw_fields)
    for i, f in reversed(tuple(enumerate(raw_fields))):
        replacement = replacements.get(f)
        if replacement is None:
            continue
        raw_fields[i:(i + 1)] = reversed(replacement)
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
                assert isinstance(d.name, Late)

                def_name = d.name.name

                try:
                    op_val = eval_def_rvalue(d.value, ns)
                except:
                    print("%d: %r: exception during evaluation" % (
                        sline.n, str(sline)
                    ))
                    raise

                ns[def_name] = op_val
                if def_name in instruction_attributes:
                    attrs[def_name] = op_val

    block = heading.child

    for attr, val_str in attrs.items():
        setattr(insn, attr, instruction_attributes[attr](val_str))

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


def parse_multiline(parser, heading, **parse_kw):
    code = str(heading)

    if not code:
        return None, None

    try:
        return parser.parse(code, **parse_kw), False
    except SyntaxError:
        # try to parse line with it's block as multiline statement
        block = heading.child
        if not block:
            raise

        block_code = code

        prev_have_child = False
        for line in block:
            if line.child:
                if prev_have_child:
                    # only last line is alowed to have block
                    raise
                prev_have_child = True

            block_code += " " + str(line)

        if block_code == code:
            raise

        try:
            res = parser.parse(block_code, **parse_kw)
        except SyntaxError:
            res = None
        else:
            return res, True

        if res is None:
            # need to `raise` first `SyntaxError`
            raise


def parse_short_statement(heading, **parse_kw):
    stmnt, multiline = parse_multiline(
        ShortStatement, heading, **parse_kw
    )
    if stmnt:
        if multiline:
            heading.multiline = True
        return [stmnt]
    else:
        return []


def parse_lines(heading):
    block = heading.child

    if block is None:
        return

    for line in block:
        try:
            stmnts = parse_short_statement(line, debug = False)
        except SyntaxError:
            # before debug call stack another exception
            msg = format_exc()
            try:
                parse_short_statement(line, debug = True)
            except SyntaxError:
                pass
            # after parser log printed
            print("%d: %r:" % (line.n, str(line)))
            print(msg)
            raise
        else:
            comment = "".join(line.iter_comment()).strip()
            if comment:
                stmnts.insert(0, Comment(comment))

            if stmnts:
                line.stmnts = stmnts

        parse_lines(line.root)


class MergeContext(object):

    def __init__(self):
        self.for_loops = set()

    def merge_statements(self, heading):
        block = heading.child

        if block is None:
            return

        sub_stmnts = []
        for line in block:
            self.merge_statements(line)
            sub_stmnts.extend(line.stmnts)

        sub_stmnts = list(iter_join_BranchElse(sub_stmnts))

        if not sub_stmnts:
            return

        stmnts = heading.stmnts
        if stmnts:
            last_stmnt = stmnts[-1]
            if not isinstance(last_stmnt, CBlock):

                for_stmnt = None
                for i, s in enumerate(sub_stmnts):
                    if isinstance(s, LoopFor) and s not in self.for_loops:
                        if for_stmnt is not None:
                            raise SyntaxError(
        "%s: %r: multiple loop statements in block" % (heading.n, str(heading))
                            )
                        for_stmnt = i, s

                if for_stmnt is None:
                    last_stmnt = BranchIf(last_stmnt)
                else:
                    i, s = for_stmnt
                    del sub_stmnts[i]
                    s.cond = last_stmnt
                    last_stmnt = s
                    if s.children:
                        raise NotImplementedError(
                "%s: %r: children of `for` block are to be moved to `step`" % (
                                heading.n, heading
                            )
                        )

                    self.for_loops.add(s)

                stmnts[-1] = last_stmnt

            last_stmnt(*sub_stmnts)
        else:
            heading.stmnts = sub_stmnts


def iter_join_BranchElse(stmnts):
    prev_stmnt = None
    for stmnt in stmnts:

        if isinstance(stmnt, BranchElse):
            if not isinstance(prev_stmnt, BranchIf):
                raise SyntaxError("%s must follow BranchIf, not %s" % (
                    type(stmnt).__name__, type(prev_stmnt).__name__
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

    arg("short_desc_file_names",
        nargs = "+",
    )
    arg("-r", "--read-bitsize",
        default = 32,
        type = int,
        help = "bitsize of word",
    )
    arg("--swap",
        action = "store_true",
        help = "split instructions encoding fields by word boundary"
            " and swap words",
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
    arg("-J", "--no-join",
        action = "store_true",
        help = "do not join neighboring opcodes",
    )
    # TODO: option to join consecutive opcodes

    args = ap.parse_args()
    read_bitsize = args.read_bitsize
    output_file_name = args.output_file_name

    short_desc = ""

    for file_name in args.short_desc_file_names:
        with open(file_name, "r") as f:
            if not short_desc.endswith("\n"):
                short_desc += "\n"
            short_desc += f.read()

    bp = CBlockParser()
    top = bp.parse(short_desc)

    top.strip_comments()

    # analyze instructions

    insn_lines = []
    decl_lines = []

    for top_line in top.child:
        analyze_instruction_block(top_line)

        parse_lines(top_line.root)

        insn = top_line.insn
        if insn is not None:
            insn.read_bitsize = read_bitsize
            insn_lines.extend(iter_multiply_instruction_blocks(top_line))

        decls = top_line.decls
        if decls is not None:
            decl_lines.append(top_line)

    # Handle declarations

    types = NamedList(
        list_name = args.types_list_name
    )

    for heading in decl_lines:
        root = heading.root
        for t in heading.decls:

            if isinstance(t, Function):
                MergeContext().merge_statements(root)
                t.body = BodyTree(children = root.stmnts)

            types.append(t)

    # handle instructions

    insts = NamedList(
        list_name = args.list_name,
    )

    join_op = not args.no_join
    swap = args.swap

    # User can produce duplicates in source code.
    # So, it's error in user code.
    # User to be notified.
    duplicates = defaultdict(list)

    for heading in insn_lines:
        i = heading.insn
        root = heading.root

        set_attributes(root)

        if i.mnemonic == "skip":
            continue

        if swap:
            i.swap_fields_by_word(read_bitsize)

        if join_op:
            i.join_opcodes()

        MergeContext().merge_statements(root)

        i.semantics = root.stmnts

        code = dump_insn(i)
        same_insts = duplicates[code]
        same_insts.append(i)
        if 1 < len(duplicates[code]):
            continue

        handle_insn(i,
            print_disas_format = args.print_disas_format,
            print_semantics = args.print_semantics,
        )
        insts.append(i)

    if output_file_name:
        insts_text = dump_insn(insts)
        types_text = dumps(types, imports = False)
        with open(output_file_name, "w") as f:
            f.write("# this file is generated by " + ap.prog + "\n")
            f.write("from qemu import *\n")
            f.write("from source import *\n")
            f.write("\n")
            f.write(insts_text + "\n")

            if types:
                f.write("\n")
                f.write(types_text + "\n")

    if args.print_semantics:
        for t in types:
            # After output was produced, it's safe to do some changes.
            LateLinker(t).visit()

            if isinstance(t, Function):
                # Note: can't use regular chunks mechanism until fully linked.
                print_function(t)
            elif isinstance(t, Variable):
                print(check_cols_fix_up(
                    t.declaration_string
                  + gen_init_string(
                        t.type,
                        t.initializer,
                        "    "
                    )
                  + "\n"
                ))

    if duplicates:
        print(
            "Duplicates:\n\t"
          + "\n\t".join(
                ("%s: %d" % (d[0].mnemonic, len(d)))
                    for __, d in sorted(i
                        for i in  duplicates.items() if 1 < len(i[1])
                    )
            )
          + "\n"
        )

    print("Total instructions: %d" % len(insts))

    encodings = separate_instructions(insts)

    for e in encodings.values():
        mnemonic_cnt = defaultdict(int)
        for i in e.instructions:
            mnemonic_cnt[i.mnemonic] += 1

        if mnemonic_cnt:
            print(" Encoding: %s\n Instructions: %d" % (
                e.name,
                sum(mnemonic_cnt.values())
            ))
            max_len = max(len(n) for n in mnemonic_cnt)
            fmt = "  %%%ds: %%d" % max_len
            for n, c in sorted(mnemonic_cnt.items()):
                print(fmt % (n, c))

if __name__ == "__main__":
    exit(main() or 0)
