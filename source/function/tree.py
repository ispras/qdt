__all__ = [
    "Node"
      , "Comment"
      , "Label"
      , "NewLine"
      , "MacroBranch"
      , "LoopWhile"
      , "LoopDoWhile"
      , "LoopFor"
      , "BranchIf"
      , "BranchSwitch"
      , "BranchElse"
      , "SwitchCase"
      , "SwitchCaseDefault"
      , "StrConcat"
      , "Ifdef"
      , "Endif"
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
                  , "OpPredDec"
                  , "OpPostDec"
                  , "OpPredInc"
                  , "OpPostInc"
                  , "OpDeref"
                  , "OpNot"
                  , "OpCast"
              # BinaryOperator
                  , "OpAssign"
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
                  , "OpCaseRange"
]

from ..c_const import (
    CConst,
    CINT
)
from ..model import (
    Type,
    Pointer,
    Variable
)
from common import (
    lazy,
    ObjectVisitor,
    BreakVisiting
)
from six import (
    integer_types
)


class CPPStr(object):
    "Class stores the string used while the preprocessor is running"

    def __init__(self, val):
        self.val = val

    def __c__(self, writer):
        writer.write(self.val)


class DeclarationInChildrenSearcher(ObjectVisitor):

    def __init__(self, root):
        super(DeclarationInChildrenSearcher, self).__init__(root,
            field_name = "__node__"
        )
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
        indent_children = True,
        children = []
    ):
        self.indent_children = indent_children
        self.children = []
        for child in children:
            self.add_child(child)

    def __call__(self, *children):
        for c in children:
            self.add_child(c)
        return self

    def add_child(self, child):
        if isinstance(child, str):
            child = CConst.parse(child)
        elif isinstance(child, integer_types):
            child = CINT(child)

        self.children.append(child)

    def out_children(self, writer):
        if self.indent_children:
            writer.push_indent()

        for child in self.children:
            child.__c__(writer)
            if isinstance(child, SemicolonPresence):
                writer.line(";")

        if self.indent_children:
            writer.pop_indent()


class Comment(Node):

    def __init__(self, text):
        super(Comment, self).__init__()
        self.text = text

    def __c__(self, writer):
        writer.line("/*@s" + self.text.replace(" ", "@s") + "@s*/")


class Label(Node):

    def __init__(self, name):
        super(Label, self).__init__()
        self.name = name

    def __c__(self, writer):
        writer.push_state(reset = True)
        writer.line(self.name + ":")
        writer.pop_state()


class NewLine(Node):

    def __init__(self):
        super(NewLine, self).__init__()

    def __c__(self, writer):
        writer.line("")


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
        writer.line("}")


class LoopWhile(Node):

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
        writer.line("}")


class LoopDoWhile(Node):

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
        writer.line(");")


class LoopFor(Node):

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
        writer.line("}")


class BranchIf(Node):

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

        writer.line("}")


class BranchElse(Node):
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


class BranchSwitch(Node):

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
            old_ch = self.children
            new_ch = [ old_ch[0] ]
            for ch in old_ch[1:]:
                new_ch.append(NewLine())
                new_ch.append(ch)
            self.children = new_ch

        writer.write("switch@b(")
        self.var.__c__(writer)
        writer.line(")@b{")
        self.out_children(writer)
        writer.line("}")


class SwitchCase(Node):

    def __init__(self, const, add_break = True):
        super(SwitchCase, self).__init__()
        self.add_break = add_break

        if isinstance(const, integer_types):
            const = CINT(const)

        self.const = const

    def __c__(self, writer):
        if self.add_break:
            self.add_child(Break())

        ds= DeclarationInChildrenSearcher(self)
        ds.visit()

        writer.write("case@b")
        self.const.__c__(writer)
        if ds.have_declaration:
            writer.line(":@b{")
            self.out_children(writer)
            writer.line("}")
        else:
            writer.line(":")
            self.out_children(writer)


class SwitchCaseDefault(Node):

    def __init__(self, add_break = True):
        super(SwitchCaseDefault, self).__init__()
        self.add_break = add_break

    def __c__(self, writer):
        if self.add_break:
            self.add_child(Break())

        ds = DeclarationInChildrenSearcher(self)
        ds.visit()

        if ds.have_declaration:
            writer.line("default:@b{")
            self.out_children(writer)
            writer.line("}")
        else:
            writer.line("default:")
            self.out_children(writer)


class StrConcat(Node):

    def __init__(self, *args, **kw_args):
        super(StrConcat, self).__init__(children = args)
        self.delim = kw_args.get("delim", "")

    def __c__(self, writer):
        first_child = self.children[0]
        first_child.__c__(writer)

        for c in self.children[1:]:
            writer.write(self.delim)
            c.__c__(writer)


class Ifdef(Node):

    def __init__(self, val):
        super(Ifdef, self).__init__()
        if isinstance(val, str):
            self.val = CPPStr(val)
        else:
            self.val = val

    def __c__(self, writer):
        writer.push_state(reset = True)
        writer.write("#ifdef ")
        self.val.__c__(writer)
        writer.line()
        writer.pop_state()


class Endif(Node):
    def __init__(self):
        super(Endif, self).__init__()

    def __c__(self, writer):
        writer.push_state(reset = True)
        writer.line("#endif")
        writer.pop_state()


class SemicolonPresence(Node):
    """ SemicolonPresence class is used to decide when
    to print semicolon.
    """


class Break(SemicolonPresence):

    def __init__(self):
        super(Break, self).__init__()

    def __c__(self, writer):
        writer.write("break")


class Call(SemicolonPresence):

    __type_references__ = ("children", "type")

    def __init__(self, func, *args):
        super(Call, self).__init__(children = args)

        self.func = func
        if isinstance(func, str):
            self.type = Type.lookup(func)
        elif isinstance(func, Variable) or isinstance(func, OpSDeref):
            # Pointer to the function
            self.type = func
        else:
            raise ValueError(
                "Invalid type of func in Call: " + type(func).__name__
            )

    def __c__(self, writer):
        if isinstance(self.func, OpSDeref):
            self.func.__c__(writer)
        else:
            writer.write(self.type.name)


        writer.write("(@a")
        if self.children:
            first_child = self.children[0]
            first_child.__c__(writer)

            for c in self.children[1:]:
                writer.write(",@s")
                c.__c__(writer)

        writer.write(")")


class Declare(SemicolonPresence):

    def __init__(self, *variables):

        super(Declare, self).__init__(children = variables)

    def add_child(self, child):
        super(Declare, self).add_child(child)

        if isinstance(child, OpAssign):
            if not isinstance(child.children[0], Variable):
                raise TypeError(
                    "Wrong child type: expected Variable"
                )
        elif not isinstance(child, Variable):
            raise TypeError(
                "Wrong child type: expected Variable or OpAssign"
            )

    def __c__(self, writer):
        child = self.children[0]
        if isinstance(child, OpAssign):
            v = child.children[0]
        else:
            v = child

        if v.static:
            writer.write("static@b")
        if v.const:
            writer.write("const@b")

        v_type = v.type
        asterisks = "@b"
        while isinstance(v_type, Pointer):
            v_type = v_type.type
            asterisks += "*"
        writer.write(v_type.name + asterisks)
        child.__c__(writer)

        for child in self.children[1:]:
            if isinstance(child, OpAssign):
                v = child.children[0]
            else:
                v = child

            asterisks = ""
            t = v.type
            while isinstance(t, Pointer):
                t = t.type
                asterisks += "*"

            if t is not v_type:
                raise TypeError(
                    "All variable in Declare must have the same type"
                )

            writer.write(",@s" + asterisks)
            child.__c__(writer)


class MCall(SemicolonPresence):

    __type_references__ = ("children", "type")

    def __init__(self, macro, *args):
        super(MCall, self).__init__(children = args)
        self.type = Type.lookup(macro)

    def add_child(self, child):
        if isinstance(child, str):
            child = CPPStr(child)
        if isinstance(child, integer_types):
            child = CINT(child)

        self.children.append(child)

    def __c__(self, writer):
        writer.write(self.type.name)

        if self.children:
            writer.write("(")

            first_child = self.children[0]
            first_child.__c__(writer)

            for c in self.children[1:]:
                writer.write(",@s")
                c.__c__(writer)

            writer.write(")")


class Return(SemicolonPresence):

    def __init__(self, arg = None):
        super(Return, self).__init__()
        if arg is not None:
            self.prefix = "return" + "@b"
            self.add_child(arg)
        else:
            self.prefix = "return"

    def __c__(self, writer):
        writer.write(self.prefix)
        if self.children:
            self.children[0].__c__(writer)


class Goto(SemicolonPresence):

    def __init__(self, label):
        super(Goto, self).__init__()
        self.label = label

    def __c__(self, writer):
        writer.line("goto@b" + self.label.name)


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

        if self.children:
            first_child = self.children[0]
            first_child.__c__(writer)

            for c in self.children[1:]:
                writer.write(self.delim)
                c.__c__(writer)

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
        if isinstance(_type, Pointer):
            struct = _type.type
        else: # _type expected to be a Structure
            struct = _type

        # for type collection
        self.struct = struct

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


class OpPredDec(UnaryOperator):

    def __init__(self, var):
        super(OpPredDec, self).__init__("--", var, suffix_op = False)


class OpPostDec(UnaryOperator):

    def __init__(self, var):
        super(OpPostDec, self).__init__("--", var, suffix_op = True)


class OpPredInc(UnaryOperator):

    def __init__(self, var):
        super(OpPredInc, self).__init__("++", var, suffix_op = False)


class OpPostInc(UnaryOperator):

    def __init__(self, var):
        super(OpPostInc, self).__init__("++", var, suffix_op = True)


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


class OpCaseRange(BinaryOperator):

    def __init__(self, arg1, arg2, parenthesis = False):
        super(OpCaseRange, self).__init__("...", arg1, arg2, parenthesis)


op_priority = {
    OpIndex:      1,
    OpSDeref:     1,
    OpPredDec:    1,
    OpPostDec:    1,
    OpPredInc:    1,
    OpPostInc:    1,
    OpCaseRange:  1,
    OpDeref:      2,
    OpAddr:       2,
    OpNot:        2,
    OpLogNot:     2,
    OpCast:       2,
    OpMul:        3,
    OpDiv:        3,
    OpRem:        3,
    OpAdd:        4,
    OpSub:        4,
    OpLShift:     5,
    OpRShift:     5,
    OpGE:         6,
    OpLE:         6,
    OpGreater:    6,
    OpLower:      6,
    OpEq:         7,
    OpNEq:        7,
    OpAnd:        8,
    OpXor:        9,
    OpOr:         10,
    OpLogAnd:     11,
    OpLogOr:      12,
    OpAssign:     13,
    OpCombAssign: 13,
}
