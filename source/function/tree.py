__all__ = [
    "Node"
      , "Comment"
      , "NewLine"
      , "MacroBranch"
      , "Ifdef"
      , "CNode"
          , "CId"
          , "Label"
          , "CBlock"
              , "CCondBlock"
                  , "LoopWhile"
                  , "LoopDoWhile"
                  , "BranchIf"
                  , "BranchElse"
                  , "LoopFor"
              , "BranchSwitch"
              , "SwitchCase"
              , "SwitchCaseDefault"
          , "StrConcat"
          # SemicolonPresence
              , "Break"
              , "Call"
              , "Goto"
              , "Declare"
              , "MCall"
              , "Return"
              # Operator
                  , "OpCast"
                  , "OpIndex"
                  , "OpSDeref"
                  # UnaryOperator
                      , "OpAddr"
                      , "OpDec"
                      , "OpInc"
                      , "OpPostDec"
                      , "OpPostInc"
                      , "OpPreDec"
                      , "OpPreInc"
                      , "OpDeref"
                      , "OpNot"
                      , "OpMinus"
                      , "OpPlus"
                      , "OpSizeOf"
                  , "BinaryOperator"
                      , "OpAssign"
                      , "OpDeclareAssign"
                      , "OpCombAssign"
                      , "OpAdd"
                      , "OpSub"
                      , "OpMul"
                      , "OpDiv"
                      , "OpRem"
                      , "OpAnd"
                      , "OpOr"
                      , "OpXor"
                      , "OpLShift"
                      , "OpRShift"
                      , "OpRotR"
                      , "OpLogAnd"
                      , "OpLogOr"
                      , "OpLogNot"
                      , "OpEq"
                      , "OpNEq"
                      , "OpGE"
                      , "OpLE"
                      , "OpGreater"
                      , "OpLess"
                      , "CaseRange"
                  , "OpTernCond"
  , "define_python_operators"
  , "flat_list"
]

from ..c_const import (
    CConst,
    CINT
)
from ..model import (
    Type,
    Pointer,
    Macro,
    NodeVisitor,
    Function,
    Variable
)
from ..type_container import (
    TypeContainer,
)
from common import (
    ee,
    SkipVisiting,
)
from six import (
    integer_types
)
from types import (
    GeneratorType
)
from functools import (
    update_wrapper,
)


# OpSDeref is automatically re-directed to definition of structure if
# available.
OPSDEREF_FROM_DEFINITION = ee("QDT_OPSDEREF_FROM_DEFINITION", "True")


class DeclarationSearcher(NodeVisitor):

    def __init__(self, root, **kw):
        super(DeclarationSearcher, self).__init__(root, **kw)
        self.have_declaration = False

    def __visit__(self, cur):
        if isinstance(cur, Declare):
            self.have_declaration = True
            raise SkipVisiting()


def flat_iter(gen):
    stack = [gen]
    while stack:
        cur = stack[-1]
        for i in cur:
            if isinstance(i, GeneratorType):
                stack.append(i)
                # start yielding items from `i`
                break
            else:
                yield i
        else:
            # cur is empty
            stack.pop()


def flat_list(gen):
    ret = lambda *a, **kw: list(flat_iter(gen(*a, **kw)))
    update_wrapper(ret, gen)
    return ret


class Node(TypeContainer):

    # traverse order indicator for `ObjectVisitor`
    __node__ = ("children",)
    __type_references__ = __node__
    __pygen_deps__ = __node__

    # `val`ue must be defined by descendant class explicitly
    val = ""
    new_line = ""
    indent_children = True

    def __init__(self,
        children = [],
        **kw
    ):
        super(Node, self).__init__(**kw)
        self.children = []
        for child in children:
            self.add_child(child)

    def __gen_code__(self, gen):
        gen.gen_code(self, skip_kw = ("children",))
        if self.children:
            gen.line(gen.nameof(self) + "(")
            gen.push_indent()
            gen.pprint_join(",", self.children)
            gen.pop_indent()
            gen.line()
            gen.line(")")

    def __call__(self, *children):
        self.add_children(children)
        return self

    def add_child(self, child):
        if isinstance(child, GeneratorType):
            self.children.extend(flat_iter(child))
        else:
            self.children.append(child)

    def add_children(self, children):
        add_child = self.add_child
        for c in children:
            add_child(c)

    def out_children(self, writer):
        if self.indent_children:
            writer.push_indent()

        for child in self.children:
            child.__c__(writer)
            if child.new_line is not None:
                writer.line(child.new_line)

        if self.indent_children:
            writer.pop_indent()

    def __c__(self, writer):
        writer.write(self.val)
        self.out_children(writer)


class Ifdef(Node):

    __node__ = Node.__node__ + ("cond",)
    __type_references__ = __node__
    __pygen_deps__ = __node__

    new_line = None
    indent_children = False

    def __init__(self, cond, *children, **kw):
        super(Ifdef, self).__init__(
            children = children,
            **kw
        )
        self.cond = cond

    def __c__(self, writer):
        with writer.cpp:
            writer.line("ifdef@b" + self.val)
            writer.push_indent()
        self.out_children(writer)
        with writer.cpp:
            writer.pop_indent()
            writer.line("endif")

    @property
    def val(self):
        cond = self.cond
        if isinstance(cond, Macro):
            return cond.c_name
        return cond


class CNode(Node):

    def add_child(self, child):
        if isinstance(child, str):
            child = CConst.parse(child)
        elif isinstance(child, integer_types):
            child = CINT(child)

        super(CNode, self).add_child(child)

    @staticmethod
    def out_child(child, writer):
        child.__c__(writer)


class CId(CNode):
    "C Identifier"
    new_line = None

    def __init__(self, val, **kw):
        super(CId, self).__init__(**kw)
        self.val = val


class Comment(Node):

    def __init__(self, text, **kw):
        super(Comment, self).__init__(**kw)
        self.text = text

    @property
    def val(self):
        return "/*@s" + self.text.replace(" ", "@s") + "@s*/"


class Label(CNode):

    new_line = ":"

    def __init__(self, name, **kw):
        if not isinstance(name, CId):
            name = CId(name)
        super(Label, self).__init__(children = [name], **kw)

    def __c__(self, writer):
        # A label must be written without an indent.
        writer.save_indent()
        super(Label, self).__c__(writer)
        writer.load_indent()

    @property
    def name(self):
        return self.id.val

    @property
    def id(self):
        return self.children[0]


class NewLine(Node):
    pass


class MacroBranch(Node):
    """ MacroBranch describes construction like MACRO(x, y) { ... } """

    __node__ = Node.__node__ + ("macro_call",)
    __type_references__ = ("macro_call",)
    __pygen_deps__ = __node__

    def __init__(self, macro_call, **kw):
        super(MacroBranch, self).__init__(**kw)
        self.macro_call = macro_call

    def __c__(self, writer):
        self.macro_call.__c__(writer)
        writer.line("@b{")
        self.out_children(writer)
        writer.write("}")


class CBlock(CNode):
    pass


class CCondBlock(CBlock):
    __node__ = CBlock.__node__ + ("cond",)
    __type_references__ = ("cond",)
    __pygen_deps__ = __node__

    def __init__(self, cond):
        super(CCondBlock, self).__init__()
        self.cond = cond


class LoopWhile(CCondBlock):

    def __c__(self, writer):
        writer.write("while (")
        self.cond.__c__(writer)
        writer.line(")@b{")
        self.out_children(writer)
        writer.write("}")


class LoopDoWhile(CCondBlock):

    def __c__(self, writer):
        writer.line("do@b{")
        self.out_children(writer)
        writer.write("}@bwhile@b(")
        self.cond.__c__(writer)
        writer.write(");")


class LoopFor(CCondBlock):

    __node__ = CCondBlock.__node__ + ("init", "step",)
    __type_references__ = CCondBlock.__type_references__ + ("init", "step",)
    __pygen_deps__ = __node__

    def __init__(self, init = None, cond = None, step = None, **kw):
        super(LoopFor, self).__init__(cond, **kw)
        self.init = init
        self.step = step

    def __c__(self, writer):
        writer.write("for@b(")
        if self.init is not None:
            self.init.__c__(writer)
        writer.write(";")
        if self.cond is not None:
            writer.write("@b")
            self.cond.__c__(writer)
        writer.write(";")
        if self.step is not None:
            writer.write("@b")
            self.step.__c__(writer)
        writer.line(")@b{")
        self.out_children(writer)
        writer.write("}")


class BranchIf(CCondBlock):

    __node__ = CCondBlock.__node__ + ("else_blocks",)
    __type_references__ = CCondBlock.__type_references__ + ("else_blocks",)
    __pygen_deps__ = __node__

    def __init__(self, *a, **kw):
        super(BranchIf, self).__init__(*a, **kw)
        self.else_blocks = []

    def add_else(self, else_bl):
        self.else_blocks.append(else_bl)

    def __call__(self, *children_and_elses):
        for ce in children_and_elses:
            if isinstance(ce, BranchElse):
                self.add_else(ce)
            else:
                self.add_child(ce)

        return self

    def __c__(self, writer):
        writer.write("if@b(")
        self.cond.__c__(writer)
        writer.line(")@b{")
        self.out_children(writer)

        for e in self.else_blocks:
            e.__c__(writer)

        writer.write("}")

    def __gen_code__(self, gen):
        super(BranchIf, self).__gen_code__(gen)
        if self.else_blocks:
            gen.write(gen.nameof(self) + "(*")
            gen.pprint(self.else_blocks)
            gen.line(")")


class BranchElse(CCondBlock):
    """ BranchElse must be added to parent BranchIf node using `add_else`. """

    def __init__(self, cond = None, **kw):
        super(BranchElse, self).__init__(cond = cond, **kw)

    def __c__(self, writer):
        if self.cond is not None:
            writer.write("}@belse@bif@b(")
            self.cond.__c__(writer)
            writer.line(")@b{")
        else:
            writer.line("}@belse@b{")
        self.out_children(writer)


class BranchSwitch(CBlock):

    __node__ = CBlock.__node__ + ("var",)
    __type_references__ = ("var",)
    __pygen_deps__ = __node__

    indent_children = False

    def __init__(self, var,
        add_break_in_default = True,
        cases = [],
        separate_cases = False,
        **kw
    ):
        super(BranchSwitch, self).__init__(**kw)
        self.default_case = None
        self.add_break_in_default = add_break_in_default
        self.var = var
        self.separate_cases = separate_cases
        self.add_cases(cases)

    def add_child(self, case):
        if isinstance(case, SwitchCaseDefault):
            if self.default_case:
                raise ValueError("Multiple default labels in one switch")
            self.default_case = case
        self.children.append(case)

    def add_cases(self, cases):
        return self(*cases)

    def __c__(self, writer):
        if not self.default_case:
            self.add_child(SwitchCaseDefault(self.add_break_in_default))

        if self.separate_cases and self.children:
            self._add_empty_lines(self.children)

        writer.write("switch@b(")
        self.var.__c__(writer)
        writer.line(")@b{")
        self.out_children(writer)
        writer.write("}")

    @staticmethod
    def _add_empty_lines(children):
        new_ch = [ children[0] ]
        need_nl = not isinstance(new_ch[0], NewLine)
        for ch in children[1:]:
            is_not_nl = not isinstance(ch, NewLine)
            if need_nl and is_not_nl:
                new_ch.append(NewLine())
            new_ch.append(ch)
            need_nl = is_not_nl
        children[:] = new_ch


class SwitchCase(CBlock):

    def __init__(self, const, add_break = True, **kw):
        super(SwitchCase, self).__init__(**kw)
        self.add_break = add_break

        if isinstance(const, integer_types):
            const = CINT(const)
        elif isinstance(const, tuple):
            const = CaseRange(*const)

        self.const = const

    @property
    def new_line(self):
        if DeclarationSearcher(self).visit().have_declaration:
            return "}"
        else:
            return None

    def __c__(self, writer):
        if (   self.add_break
            and (   self.children
                 and not isinstance(self.children[-1], Break)
                 or not self.children
            )
        ):
            self.add_child(Break())

        writer.write("case@b")
        self.const.__c__(writer)
        if DeclarationSearcher(self).visit().have_declaration:
            writer.line(":@b{")
            self.out_children(writer)
        else:
            writer.line(":")
            self.out_children(writer)


class SwitchCaseDefault(CBlock):

    def __init__(self, add_break = True, **kw):
        super(SwitchCaseDefault, self).__init__(**kw)
        self.add_break = add_break

    @property
    def new_line(self):
        if DeclarationSearcher(self).visit().have_declaration:
            return "}"
        else:
            return None

    def __c__(self, writer):
        if (   self.add_break
            and (   self.children
                 and not isinstance(self.children[-1], Break)
                 or not self.children
            )
        ):
            self.add_child(Break())

        if DeclarationSearcher(self).visit().have_declaration:
            writer.line("default:@b{")
            self.out_children(writer)
        else:
            writer.line("default:")
            self.out_children(writer)


# TODO: joining "a""b" to "ab". Optionally? By a helper function?
class StrConcat(CNode):

    def __init__(self, *children, **kw_args):
        delim = kw_args.get("delim", "")
        super(StrConcat, self).__init__(children = children, **kw_args)
        self.delim = delim

    def __c__(self, writer):
        writer.join(self.delim, self.children, self.out_child)


class SemicolonPresence(CNode):
    "SemicolonPresence class is used to decide when to print semicolon."

    new_line = ";"


class Break(SemicolonPresence):

    val = "break"


class Call(SemicolonPresence):

    def __init__(self, func, *args, **kw):
        if isinstance(func, str):
            func = Type[func]
        elif not isinstance(func, (Variable, Function, CNode)):
            raise ValueError(
                "Invalid type of func in Call: " + type(func).__name__
            )

        super(Call, self).__init__(children = (func,) + args, **kw)

    @property
    def func(self):
        return self.children[0]

    @property
    def args(self):
        return self.children[1:]

    def __c__(self, writer):
        self.func.__c__(writer)

        writer.write("(@a")
        writer.join(",@s", self.args, self.out_child)
        writer.write("@c)")

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.pprint(self.func)
        if self.args:
            # visually delimit func and args
            gen.write(")(")
            gen.pprint_join(", ", self.args, per_line = False)
        gen.line(")")


class Declare(SemicolonPresence):

    def __init__(self, *variables, **kw):
        super(Declare, self).__init__(children = variables, **kw)

    def iter_variables(self):
        for child in self.children:
            if isinstance(child, OpDeclareAssign):
                yield child.variable
            else:
                yield child

    def add_child(self, child):
        if isinstance(child, OpDeclareAssign):
            if not isinstance(child.children[0], Variable):
                raise TypeError(
                    "Wrong child type: expected Variable"
                )
            var = child.children[0]
        elif isinstance(child, Variable):
            var = child
        else:
            raise TypeError(
                "Wrong child type: expected Variable or OpDeclareAssign"
            )

        if self.children:
            first_child = self.children[0]
            if isinstance(first_child, OpDeclareAssign):
                v = first_child.children[0]
            else:
                v = first_child
            if (   v.full_deref != var.full_deref
                or v.static != var.static
                or v.const != var.const
            ):
                raise TypeError("All variables in Declare must have the same"
                    " type and qualifiers"
                )

        super(Declare, self).add_child(child)

    def __c__(self, writer):
        child = self.children[0]
        if isinstance(child, OpDeclareAssign):
            v = child.children[0]
        else:
            v = child

        if v.static:
            writer.write("static@b")
        if v.const:
            writer.write("const@b")

        writer.write(v.full_deref.c_name + "@b" + v.asterisks)
        self._write_child(child, writer)

        for child in self.children[1:]:
            if isinstance(child, OpDeclareAssign):
                v = child.children[0]
            else:
                v = child

            writer.write(",@s" + v.asterisks)
            self._write_child(child, writer)

    @staticmethod
    def _write_child(child, writer):
        if isinstance(child, Variable):
            if child.array_size is not None:
                if not child.used:
                    writer.write("__attribute__((unused))@b")
                child.__c__(writer)
                writer.write("[%d]" % child.array_size)
            else:
                child.__c__(writer)
                if not child.used:
                    writer.write("@b__attribute__((unused))")
            if child.initializer:
                writer.write("@b=@s")
                writer.write(child.type.gen_usage_string(child.initializer))
        else:
            child.__c__(writer)


class MCall(SemicolonPresence):

    __type_references__ = ("type",)

    def __init__(self, macro, *args, **kw):
        super(MCall, self).__init__(children = args, **kw)
        self.macro = macro

    @property
    def type(self):
        macro = self.macro
        if isinstance(macro, Macro):
            return macro
        else:
            return Type[macro]

    def __c__(self, writer):
        writer.write(self.type.c_name)

        if self.children:
            writer.write("(@a")
            writer.join(",@s", self.children, self.out_child)
            writer.write("@c)")


class Return(SemicolonPresence):

    def __init__(self, *child, **kw):
        super(Return, self).__init__(**kw)
        self(*child)

    @property
    def val(self):
        if self.children:
            return "return@b"
        else:
            return "return"

    def __c__(self, writer):
        writer.write(self.val)
        if self.children:
            self.children[0].__c__(writer)


class Goto(SemicolonPresence):

    val = "goto@b"

    def __init__(self, label, **kw):
        if isinstance(label, Label):
            label = label.id
        if not isinstance(label, CId):
            label = CId(label)
        super(Goto, self).__init__(children = [label], **kw)

    @property
    def label(self):
        return self.children[0]


class Operator(SemicolonPresence):

    prefix = ""
    delim = "@s"
    suffix = ""
    prior = None

    def __init__(self, *children, **kw_args):
        # `prior`ity can be defined at `class` level.
        # This is for custom operators mostly.
        # TODO: define all `prior`ities in that way?
        if self.prior is None:
            self.prior = op_priority[type(self)]
        super(Operator, self).__init__(children = children)

        self.parenthesis = kw_args.get("parenthesis", False)

    def add_child(self, child):
        super(Operator, self).add_child(child)

        if isinstance(child, Operator):
            if self.prior < child.prior:
                child.parenthesis = True

    def _write_children(self, writer):
        writer.join(self.delim, self.children, self.out_child)

    def __c__(self, writer):
        if self.parenthesis:
            writer.write("(")

        writer.write(self.prefix)
        self._write_children(writer)
        writer.write(self.suffix)
        if self.parenthesis:
            writer.write(")")

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.pprint_join(", ", self.children, per_line = False)
        if self.parenthesis:
            gen.first_field = False
            gen.push_indent()
            gen.gen_field("parenthesis = ")
            gen.pprint(self.parenthesis)
        gen.gen_end()


class OpCast(Operator):

    prefix = "("
    delim = ")"

    def __init__(self, type_or_name, arg, **kw):
        if isinstance(type_or_name, str):
            type_or_name = Type[type_or_name]
        super(OpCast, self).__init__(type_or_name, arg, **kw)


class OpIndex(Operator):

    delim = "["
    suffix = "]"
    prior = 1

    def add_child(self, child):
        # Note, ignore `Operator.add_child` to suppress unnecessary parentheses
        super(Operator, self).add_child(child)


class OpSDeref(Operator):

    prior = 1

    def __init__(self, value, field, **kw):
        if isinstance(field, CId):
            pass
        elif isinstance(field, str):
            field = CId(field)
        else:
            raise ValueError(
                "Invalid type of field in OpSDeref: " + type(field).__name__
            )

        super(OpSDeref, self).__init__(value, field, **kw)

    @property
    def struct(self):
        struct = self.container.type
        # Note, pointer nesting must be at most 1.
        if isinstance(struct, Pointer):
            struct = struct.type

        if OPSDEREF_FROM_DEFINITION:
            struct = struct.definition

        try:
            struct.fields[self.field]
        except KeyError:
            raise RuntimeError('Structure "%s" has no field "%s"' % (
                struct, self.field
            ))

        return struct

    @property
    def type(self):
        return self.struct.fields[self.field].type

    @property
    def delim(self):
        if isinstance(self.container.type, Pointer):
            return "->"
        else:
            return "."

    @property
    def container(self):
        return self.children[0]

    @property
    def field(self):
        return self.children[1].val


class UnaryOperator(Operator):
    pass


class OpInc(UnaryOperator):

    suffix = "++"
    prior = 1


class OpDec(UnaryOperator):

    suffix = "--"
    prior = 1


OpPostDec = OpDec


OpPostInc = OpInc


class OpPreDec(UnaryOperator):

    prefix = "--"
    prior = 1


class OpPreInc(UnaryOperator):

    prefix = "++"
    prior = 1


class OpSizeOf(UnaryOperator):

    prefix = "sizeof("
    suffix = ")"


class OpAddr(UnaryOperator):

    prefix = "&"
    prior = 2


class OpDeref(UnaryOperator):

    prefix = "*"
    prior = 2


class OpLogNot(UnaryOperator):

    prefix = "!"


class OpNot(UnaryOperator):

    prefix = "~"
    prior = 2


class OpMinus(UnaryOperator):

    prefix = "-"


class OpPlus(UnaryOperator):

    prefix = "+"


class BinaryOperator(Operator):

    # subclass must define `op_str`

    @property
    def delim(self):
        return "@b" + self.op_str + "@s"


class OpAssign(BinaryOperator):

    op_str = "="


class OpDeclareAssign(BinaryOperator):

    op_str = "="

    @staticmethod
    def out_child(child, writer):
        if isinstance(child, Variable):
            if child.array_size is not None:
                if not child.used:
                    writer.write("__attribute__((unused))@b")
                child.__c__(writer)
                writer.write("[%d]" % child.array_size)
            else:
                child.__c__(writer)
                if not child.used:
                    writer.write("@b__attribute__((unused))")
        else:
            child.__c__(writer)

    @property
    def variable(self):
        return self.children[0]


class OpCombAssign(BinaryOperator):

    def __init__(self, arg1, arg2, op_sym, **kw):
        super(OpCombAssign, self).__init__(arg1, arg2, **kw)
        self.op_sym = op_sym

    @property
    def op_str(self):
        return self.op_sym + "="

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.pprint_join(", ", self.children + [self.op_sym],
            per_line = False
        )
        if self.parenthesis:
            gen.first_field = False
            gen.push_indent()
            gen.gen_field("parenthesis = ")
            gen.pprint(self.parenthesis)
        gen.gen_end()


class OpAdd(BinaryOperator):

    op_str = "+"


class OpSub(BinaryOperator):

    op_str = "-"


class OpMul(BinaryOperator):

    op_str = "*"


class OpDiv(BinaryOperator):

    op_str = "/"


class OpRem(BinaryOperator):

    op_str = "%"


class OpAnd(BinaryOperator):

    op_str = "&"


class OpOr(BinaryOperator):

    op_str = "|"


class OpXor(BinaryOperator):

    op_str = "^"


class OpLShift(BinaryOperator):

    op_str = "<<"


class OpRShift(BinaryOperator):

    op_str = ">>"


class OpRotR(BinaryOperator):

    op_str = ">>>"


class OpLogAnd(BinaryOperator):

    op_str = "&&"


class OpLogOr(BinaryOperator):

    op_str = "||"


class OpEq(BinaryOperator):

    op_str = "=="


class OpNEq(BinaryOperator):

    op_str = "!="


class OpGE(BinaryOperator):

    op_str = ">="


class OpLE(BinaryOperator):

    op_str = "<="


class OpGreater(BinaryOperator):

    op_str = ">"


class OpLess(BinaryOperator):

    op_str = "<"


class CaseRange(BinaryOperator):

    op_str = "..."
    prior = 1


class OpTernCond(Operator):

    def __init__(self, cond, true_val, false_val, **kw):
        super(OpTernCond, self).__init__(cond, true_val, false_val, **kw)

    def _write_children(self, writer):
        cond, true_val, false_fal = self.children

        self.out_child(cond, writer)

        writer.write(self.delim)
        writer.write("?")
        writer.write(self.delim)

        self.out_child(true_val, writer)

        writer.write(self.delim)
        writer.write(":")
        writer.write(self.delim)

        self.out_child(false_fal, writer)


op_priority = {
    OpLogNot:        2,
    OpCast:          2,
    OpSizeOf:        2,
    OpMinus:         2,
    OpPlus:          2,
    OpMul:           3,
    OpDiv:           3,
    OpRem:           3,
    OpAdd:           4,
    OpSub:           4,
    OpLShift:        5,
    OpRShift:        5,
    OpRotR:          5,
    OpGE:            6,
    OpLE:            6,
    OpGreater:       6,
    OpLess:          6,
    OpEq:            7,
    OpNEq:           7,
    OpAnd:           8,
    OpXor:           9,
    OpOr:            10,
    OpLogAnd:        11,
    OpLogOr:         12,
    OpAssign:        13,
    OpDeclareAssign: 13,
    OpCombAssign:    13,
    OpTernCond:      13,
}


def define_python_operators(cls):
    """ Define Python operators for some types to make function tree
construction simpler. Can be a class @decorator.
    """
    for attr, value in PYTHON_OPERATORS.items():
        if hasattr(cls, attr):
            print("%s.%s: redefined" % (cls, attr))
        setattr(cls, attr, value)
    return cls


PYTHON_OPERATORS = dict(
    __invert__ = lambda self: OpNot(self),
    __getitem__ = lambda self, key: OpIndex(self, key),
)

for name, oper in {
    "add": OpAdd,
    "and": OpAnd,
    "div": OpDiv,  # Py2 compatibility
    "truediv": OpDiv,
    "lshift": OpLShift,
    "mod": OpRem,
    "mul": OpMul,
    "or": OpOr,
    "rshift": OpRShift,
    "sub": OpSub,
    "xor": OpXor,
}.items():
    handler = lambda self, o, _oper = oper: _oper(self, o)
    PYTHON_OPERATORS["__" + name + "__"] = handler
    rhandler = lambda self, o, _oper = oper: _oper(o, self)
    PYTHON_OPERATORS["__r" + name + "__"] = rhandler

for name, oper in {
    "iadd": "+",
    "iand": "&",
    "idiv": "/",  # Py2 compatibility
    "itruediv": "/",
    "ilshift": "<<",
    "imod": "%",
    "imul": "*",
    "ior": "|",
    "irshift": ">>",
    "isub": "-",
    "ixor": "^",
}.items():
    opgen = lambda a, b, _oper = oper: OpCombAssign(a, b, _oper)
    PYTHON_OPERATORS["__" + name + "__"] = opgen


define_python_operators(CNode)
define_python_operators(Variable)
