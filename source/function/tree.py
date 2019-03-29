__all__ = [
    "Node"
      , "Comment"
      , "NewLine"
      , "MacroBranch"
      , "Ifdef"
      , "CNode"
          , "Label"
          , "LoopWhile"
          , "LoopDoWhile"
          , "LoopFor"
          , "BranchIf"
          , "BranchSwitch"
          , "BranchElse"
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
                      , "OpCast"
                  # BinaryOperator
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
                      , "OpLogAnd"
                      , "OpLogOr"
                      , "OpLogNot"
                      , "OpEq"
                      , "OpNEq"
                      , "OpGE"
                      , "OpLE"
                      , "OpGreater"
                      , "OpLower"
                      , "CaseRange"
]

from ..c_const import (
    CConst,
    CINT
)
from ..model import (
    Type,
    TypeReference,
    Pointer,
    Macro,
    NodeVisitor,
    Function,
    Variable
)
from common import (
    BreakVisiting,
    lazy
)
from six import (
    integer_types
)


class DeclarationSearcher(NodeVisitor):

    def __init__(self, root):
        super(DeclarationSearcher, self).__init__(root)
        self.have_declaration = False

    def on_visit(self):
        if isinstance(self.cur, Declare):
            self.have_declaration = True
            raise BreakVisiting()


class Node(object):

    # traverse order indicator for `ObjectVisitor`
    __node__ = ("children",)
    __type_references__ = __node__

    def __init__(self,
        val = "",
        new_line = "",
        indent_children = True,
        children = []
    ):
        self.val = val
        self.new_line = new_line
        self.indent_children = indent_children
        self.children = []
        for child in children:
            self.add_child(child)

    def __call__(self, *children):
        for c in children:
            self.add_child(c)
        return self

    def add_child(self, child):
        self.children.append(child)

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

    def __init__(self, val, *args):
        if isinstance(val, Macro):
            val = val.c_name
        super(Ifdef, self).__init__(
            # Since the macro can be undefined and unknown to the model,
            # we refer it using its string name.
            val = str(val),
            indent_children = False,
            children = args
        )
        self.new_line = None

    def __c__(self, writer):
        with writer.cpp:
            writer.line("ifdef@b" + self.val)
            writer.push_indent()
        self.out_children(writer)
        with writer.cpp:
            writer.pop_indent()
            writer.line("endif")


class CNode(Node):

    def add_child(self, child):
        if isinstance(child, str):
            child = CConst.parse(child)
        elif isinstance(child, integer_types):
            child = CINT(child)

        self.children.append(child)

    @staticmethod
    def out_child(child, writer):
        child.__c__(writer)


class Comment(Node):

    def __init__(self, text):
        super(Comment, self).__init__(
            val = "/*@s" + text.replace(" ", "@s") + "@s*/"
        )


class Label(CNode):

    def __init__(self, name):
        super(Label, self).__init__()
        self.name = name

    def __c__(self, writer):
        # A label must be written without an indent.
        writer.save_indent()
        writer.write(self.name + ":")
        writer.load_indent()


class NewLine(Node):
    pass


class MacroBranch(Node):
    """ MacroBranch describes construction like MACRO(x, y) { ... } """

    __node__ = ("children", "macro_call")
    __type_references__ = __node__

    def __init__(self, macro_call):
        super(MacroBranch, self).__init__()
        self.macro_call = macro_call

    def __c__(self, writer):
        self.macro_call.__c__(writer)
        writer.line("@b{")
        self.out_children(writer)
        writer.write("}")


class LoopWhile(CNode):

    __node__ = ("children", "cond")
    __type_references__ = __node__

    def __init__(self, cond):
        super(LoopWhile, self).__init__()
        self.cond = cond

    def __c__(self, writer):
        writer.write("while (")
        self.cond.__c__(writer)
        writer.line(")@b{")
        self.out_children(writer)
        writer.write("}")


class LoopDoWhile(CNode):

    __node__ = ("children", "cond")
    __type_references__ = __node__

    def __init__(self, cond):
        super(LoopDoWhile, self).__init__()
        self.cond = cond

    def __c__(self, writer):
        writer.line("do@b{")
        self.out_children(writer)
        writer.write("}@bwhile@b(")
        self.cond.__c__(writer)
        writer.write(");")


class LoopFor(CNode):

    __node__ = ("children", "init", "cond", "step")
    __type_references__ = __node__

    def __init__(self, init = None, cond = None, step = None):
        super(LoopFor, self).__init__()
        self.init = init
        self.cond = cond
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


class BranchIf(CNode):

    __node__ = ("children", "cond", "else_blocks")
    __type_references__ = __node__

    def __init__(self, cond):
        super(BranchIf, self).__init__()
        self.cond = cond
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


class BranchElse(CNode):
    """ BranchElse must be added to parent BranchIf node using `add_else`. """

    __node__ = ("children", "cond")
    __type_references__ = __node__

    def __init__(self, cond = None):
        super(BranchElse, self).__init__()
        self.cond = cond

    def __c__(self, writer):
        if self.cond is not None:
            writer.write("}@belse@bif@b(")
            self.cond.__c__(writer)
            writer.line(")@b{")
        else:
            writer.line("}@belse@b{")
        self.out_children(writer)


class BranchSwitch(CNode):

    __node__ = ("children", "var")
    __type_references__ = __node__

    def __init__(self, var,
        add_break_in_default = True,
        cases = [],
        child_indent = False,
        separate_cases = False
    ):
        super(BranchSwitch, self).__init__(indent_children = child_indent)
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
        for case in cases:
            self.add_child(case)

    def __call__(self, *cases):
        self.add_cases(cases)
        return self

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


class SwitchCase(CNode):

    def __init__(self, const, add_break = True):
        super(SwitchCase, self).__init__()
        self.add_break = add_break

        if isinstance(const, integer_types):
            const = CINT(const)
        elif isinstance(const, tuple):
            const = CaseRange(*const)

        self.const = const

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
            self.new_line = "}"
        else:
            writer.line(":")
            self.out_children(writer)
            self.new_line = None


class SwitchCaseDefault(CNode):

    def __init__(self, add_break = True):
        super(SwitchCaseDefault, self).__init__()
        self.add_break = add_break

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
            self.new_line = "}"
        else:
            writer.line("default:")
            self.out_children(writer)
            self.new_line = None


class StrConcat(CNode):

    def __init__(self, *args, **kw_args):
        super(StrConcat, self).__init__(children = args)
        self.delim = kw_args.get("delim", "")

    def __c__(self, writer):
        writer.join(self.delim, self.children, self.out_child)


class SemicolonPresence(CNode):
    "SemicolonPresence class is used to decide when to print semicolon."

    def __init__(self, *args, **kw_args):
        kw_args["new_line"] = ";"
        super(SemicolonPresence, self).__init__(*args, **kw_args)


class Break(SemicolonPresence):

    def __init__(self):
        super(Break, self).__init__(val = "break")


class Call(SemicolonPresence):

    def __init__(self, func, *args):
        if isinstance(func, str):
            func = Type[func]
        elif not isinstance(func, (Variable, Function, CNode)):
            raise ValueError(
                "Invalid type of func in Call: " + type(func).__name__
            )

        super(Call, self).__init__(children = (func,) + args)

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


class Declare(SemicolonPresence):

    def __init__(self, *variables):

        super(Declare, self).__init__(children = variables)

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

    __type_references__ = ("children", "type")

    def __init__(self, macro, *args):
        super(MCall, self).__init__(children = args)
        self.type = Type.lookup(macro)

    def __c__(self, writer):
        writer.write(self.type.c_name)

        if self.children:
            writer.write("(@a")
            writer.join(",@s", self.children, self.out_child)
            writer.write("@c)")


class Return(SemicolonPresence):

    def __init__(self, arg = None):
        super(Return, self).__init__()
        if arg is not None:
            self.val = "return" + "@b"
            self.add_child(arg)
        else:
            self.val = "return"

    def __c__(self, writer):
        writer.write(self.val)
        if self.children:
            self.children[0].__c__(writer)


class Goto(SemicolonPresence):

    def __init__(self, label):
        super(Goto, self).__init__(val = "goto@b" + label.name)


class Operator(SemicolonPresence):

    def __init__(self, *args, **kw_args):
        self.prior = op_priority[type(self)]
        super(Operator, self).__init__(children = args)

        self.prefix = ""
        self.delim = "@s"
        self.suffix = ""
        self.parenthesis = kw_args.get("parenthesis", False)

    def add_child(self, child):
        super(Operator, self).add_child(child)

        if isinstance(child, Operator):
            if self.prior < child.prior:
                child.parenthesis = True

    def __c__(self, writer):
        if self.parenthesis:
            writer.write("(")

        writer.write(self.prefix)
        writer.join(self.delim, self.children, self.out_child)
        writer.write(self.suffix)
        if self.parenthesis:
            writer.write(")")


class OpIndex(Operator):

    def __init__(self, var, index):
        super(OpIndex, self).__init__(var, index)
        self.delim = "["
        self.suffix = "]"


class OpSDeref(Operator):

    __type_references__ = Operator.__type_references__ + ("struct",)

    def __init__(self, value, field):
        super(OpSDeref, self).__init__(value)

        if not isinstance(field, str):
            raise ValueError(
                "Invalid type of field in OpSDeref: " + type(field).__name__
            )

        self.field = field

        _type = value.type

        struct = _type
        while isinstance(struct, (Pointer, TypeReference)):
            struct = struct.type

        # for type collection
        self.struct = struct

        try:
            if struct._definition is not None:
                struct._definition.fields[field]
            else:
                struct.fields[field]
        except KeyError:
            raise RuntimeError('Structure "%s" has no field "%s"' % (
                struct, field
            ))

        if isinstance(_type, Pointer):
            self.suffix = "->" + field
        else:
            self.suffix = "." + field

    @lazy
    def type(self):
        return self.struct.fields[self.field].type


class UnaryOperator(Operator):

    def __init__(self, op_str, arg1, suffix_op = False):
        super(UnaryOperator, self).__init__(arg1)
        if suffix_op:
            self.suffix = op_str
        else:
            self.prefix = op_str


class OpInc(UnaryOperator):

    def __init__(self, var):
        super(OpInc, self).__init__("++", var, suffix_op = True)


class OpDec(UnaryOperator):

    def __init__(self, var):
        super(OpDec, self).__init__("--", var, suffix_op = True)


OpPostDec = OpDec


OpPostInc = OpInc


class OpPreDec(UnaryOperator):

    def __init__(self, var):
        super(OpPreDec, self).__init__("--", var, suffix_op = False)


class OpPreInc(UnaryOperator):

    def __init__(self, var):
        super(OpPreInc, self).__init__("++", var, suffix_op = False)


class OpCast(UnaryOperator):

    __type_references__ = ("children", "type")

    def __init__(self, type_name, arg):
        super(OpCast, self).__init__("(" + type_name + ")", arg)
        self.type = Type.lookup(type_name)


class OpAddr(UnaryOperator):

    def __init__(self, arg1):
        super(OpAddr, self).__init__("&", arg1)


class OpDeref(UnaryOperator):

    def __init__(self, arg1):
        super(OpDeref, self).__init__("*", arg1)


class OpLogNot(UnaryOperator):

    def __init__(self, arg1):
        super(OpLogNot, self).__init__("!", arg1)


class OpNot(UnaryOperator):

    def __init__(self, arg1):
        super(OpNot, self).__init__("~", arg1)


class BinaryOperator(Operator):

    def __init__(self, op_str, arg1, arg2, parenthesis):
        super(BinaryOperator, self).__init__(arg1, arg2,
            parenthesis = parenthesis
        )
        self.delim = "@b" + op_str + "@s"


class OpAssign(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpAssign, self).__init__("=", arg1, arg2, parenthesis)


class OpDeclareAssign(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpDeclareAssign, self).__init__("=", arg1, arg2, parenthesis)

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


class OpCombAssign(BinaryOperator):

    def __init__(self, arg1, arg2, op_str, parenthesis = False):
        super(OpCombAssign, self).__init__(op_str + "=",
            arg1, arg2, parenthesis
        )


class OpAdd(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpAdd, self).__init__("+", arg1, arg2, parenthesis)


class OpSub(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpSub, self).__init__("-", arg1, arg2, parenthesis)


class OpMul(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpMul, self).__init__("*", arg1, arg2, parenthesis)


class OpDiv(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpDiv, self).__init__("/", arg1, arg2, parenthesis)


class OpRem(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpRem, self).__init__("%", arg1, arg2, parenthesis)


class OpAnd(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpAnd, self).__init__("&", arg1, arg2, parenthesis)


class OpOr(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpOr, self).__init__("|", arg1, arg2, parenthesis)


class OpXor(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpXor, self).__init__("^", arg1, arg2, parenthesis)


class OpLShift(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpLShift, self).__init__("<<", arg1, arg2, parenthesis)


class OpRShift(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpRShift, self).__init__(">>", arg1, arg2, parenthesis)


class OpLogAnd(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpLogAnd, self).__init__("&&", arg1, arg2, parenthesis)


class OpLogOr(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpLogOr, self).__init__("||", arg1, arg2, parenthesis)


class OpEq(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpEq, self).__init__("==", arg1, arg2, parenthesis)


class OpNEq(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpNEq, self).__init__("!=", arg1, arg2, parenthesis)


class OpGE(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpGE, self).__init__(">=", arg1, arg2, parenthesis)


class OpLE(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpLE, self).__init__("<=", arg1, arg2, parenthesis)


class OpGreater(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpGreater, self).__init__(">", arg1, arg2, parenthesis)


class OpLower(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpLower, self).__init__("<", arg1, arg2, parenthesis)


class CaseRange(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(CaseRange, self).__init__("...", arg1, arg2, parenthesis)


op_priority = {
    CaseRange:       1,
    OpIndex:         1,
    OpSDeref:        1,
    OpDec:           1,
    OpInc:           1,
    OpPostDec:       1,
    OpPostInc:       1,
    OpPreDec:        1,
    OpPreInc:        1,
    OpDeref:         2,
    OpAddr:          2,
    OpNot:           2,
    OpLogNot:        2,
    OpCast:          2,
    OpMul:           3,
    OpDiv:           3,
    OpRem:           3,
    OpAdd:           4,
    OpSub:           4,
    OpLShift:        5,
    OpRShift:        5,
    OpGE:            6,
    OpLE:            6,
    OpGreater:       6,
    OpLower:         6,
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
}
