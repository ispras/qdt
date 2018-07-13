__all__ = [
   "Node"
      , "Goto"
      , "Label"
      , "MacroBranch"
      , "LoopWhile"
      , "LoopDoWhile"
      , "LoopFor"
      , "BranchIf"
      , "BranchSwitch"
      , "BranchElse"
      , "SwitchCase"
      , "Comment"
      # Operator
          , "OpDec"
          , "OpInc"
          , "OpDeclare"
          , "OpIndex"
          , "OpSDeref"
          , "OpCall"
          , "OpMCall"
          , "OpBreak"
          , "OpRet"
          , "OpStrConcat"
          # UnaryOperator
              , "OpAddr"
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
]

from source import (
    Type,
    Pointer,
    Variable,
    CINT,
    CSTR
)


class Node(object):

    # traverse order indicator for `ObjectVisitor`
    __node__ = ("children",)
    __type_references__ = __node__

    def __init__(self,
            indent_children = True
        ):
        self.children = []
        self.indent_children = indent_children

    def add_child(self, child):
        if isinstance(child, str):
            child = CSTR(child)
        elif isinstance(child, int):
            child = CINT(child)

        self.children.append(child)

    def out_children(self, writer):
        if self.indent_children:
            writer.push_indent()

        for child in self.children:
            child.__c__(writer)
            if isinstance(child, Operator):
                if not isinstance(self, Operator):
                    writer.line(";")

        if self.indent_children:
            writer.pop_indent()


class Comment(Node):
    def __init__(self, value):
        super(Comment, self).__init__()
        self.text = value

    def __c__(self, writer):
        writer.line("/* " + self.text + " */")


# It describes construction like
# MACRO(x, y) { ... }
class MacroBranch(Node):

    __node__ = ("children", "macro_call")
    __type_references__ = __node__

    def __init__(self, macro_call):
        super(MacroBranch, self).__init__()
        self.macro_call = macro_call

    def __c__(self, writer):
        self.macro_call.__c__(writer)
        writer.line(" {")
        self.out_children(writer)
        writer.line("}")


class LoopWhile(Node):

    __node__ = ("children", "cond")
    __type_references__ = __node__

    def __init__(self, cond = None):
        super(LoopWhile, self).__init__()
        self.cond = cond

    def __c__(self, writer):
        writer.write("while (")
        if self.cond:
            self.cond.__c__(writer)
        writer.line(") {")
        self.out_children(writer)
        writer.line("}")


class LoopDoWhile(Node):

    __node__ = ("children", "cond")
    __type_references__ = __node__

    def __init__(self, cond = None):
        super(LoopDoWhile, self).__init__()
        self.cond = cond

    def __c__(self, writer):
        writer.line("while {")
        self.out_children(writer)
        writer.write("} while (")
        if self.cond:
            self.cond.__c__(writer)
        writer.line(");")


class LoopFor(Node):

    __node__ = ("children", "init_exp", "cond", "inc_exp")
    __type_references__ = __node__

    def __init__(self, init_exp, cond, inc_exp):
        super(LoopFor, self).__init__()
        self.init_exp = init_exp
        self.cond = cond
        self.inc_exp = inc_exp

    def __c__(self, writer):
        writer.write("for (")
        if self.init_exp:
            self.init_exp.__c__(writer)
        writer.write("; ")
        if self.cond:
            self.cond.__c__(writer)
        writer.write("; ")
        if self.inc_exp:
            self.inc_exp.__c__(writer)
        writer.line(") {")
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

    def __c__(self, writer):
        else_count = len(self.else_blocks)

        if else_count == 0:
            # ending is the keyword of next else block or "}"
            writer.line("}")
            return

        writer.write("if (")
        if self.cond:
            self.cond.__c__(writer)
        writer.line(") {")
        self.out_children(writer)

        i = 0
        while i < else_count - 1:
            self.else_blocks[i].__c__(writer)
            i += 1

        if i < else_count:
            # it's the last else block
            self.else_blocks[i].__c__(writer)
            writer.line("}")


# Don't add this class as child to any Nodes
# It should be added only by `add_else`
class BranchElse(Node):

    __node__ = ("children", "cond")
    __type_references__ = __node__

    def __init__(self, cond = None):
        super(BranchElse, self).__init__()
        self.cond = cond

    def __c__(self, writer):
        if self.cond is not None:
            writer.write("} else if (")
            self.cond.__c__(writer)
            writer.line(") {")
        else:
            writer.line("} else {")
        self.out_children(writer)


class BranchSwitch(Node):

    __node__ = ("children", "var")
    __type_references__ = __node__

    def __init__(self, var,
            add_breaks = True,
            cases = [],
            child_indent = False
        ):
        super(BranchSwitch, self).__init__(indent_children = child_indent)
        self.bodies = {}
        self.add_breaks = add_breaks
        self.add_cases(cases)
        self.var = var

        if "default" not in self.bodies:
            child = SwitchCase(None, add_breaks)
            self.bodies[str(child)] = child
            self.add_child(child)


    def add_cases(self, cases):
        for case in cases:
            if isinstance(case, SwitchCase):
                child = case
            else:
                child = SwitchCase(case, self.add_breaks)
            self.bodies[str(child)] = child
            self.add_child(child)

    def __c__(self, writer):
        writer.write("switch (")
        self.var.__c__(writer)
        writer.line(") {")
        self.out_children(writer)
        writer.line("}")


class SwitchCase(Node):

    def __init__(self, const, has_break = True):
        super(SwitchCase, self).__init__()
        self.has_break = has_break
        self.const = const

    def __str__(self):
        const = self.const
        if const:
            if isinstance(const, tuple):
                return str(const[0]) + "..." + str(const[1])
            else:
                return str(const)
        else:
            return "default"


    def __c__(self, writer):
        if self.has_break:
            self.add_child(OpBreak())

        val = str(self)
        if val != "default":
            writer.write("case ")
        writer.line(str(self) + ":")
        self.out_children(writer)


class Label(Node):

    def __init__(self, name):
        super(Label, self).__init__()
        self.name = name

    def __c__(self, writer):
        # Lable must be written whithout indent
        # That is why we set False to new_line
        writer.new_line = False
        writer.line(self.name + ":")


class Goto(Node):

    def __init__(self, lable):
        super(Goto, self).__init__()
        self.lable = lable

    def __c__(self, writer):
        writer.line("goto " + self.lable.name + ";")


class Operator(Node):

    def __init__(self, *args, **kw_args):
        super(Operator, self).__init__()
        self.prefix = ""
        self.delim = "@s"
        self.suffix = ""

        try:
            self.parenthesis = kw_args["parenthesis"]
        except KeyError:
            self.parenthesis = False

        if isinstance(self, (UnaryOperator, BinaryOperator)):
            self.prior = op_priority[type(self)]

        for arg in args:
            self.add_child(arg)

    def __c__(self, writer):
        if self.parenthesis:
            writer.write("(")

        writer.write(self.prefix)

        if self.children:
            first_child = self.children[0]

            # instance with prior
            iwp = (UnaryOperator, BinaryOperator)
            if isinstance(self, iwp) and isinstance(first_child, iwp):
                if self.prior < first_child.prior:
                    first_child.parenthesis = True

            first_child.__c__(writer)

            for c in self.children[1:]:
                writer.write(self.delim)
                if isinstance(self, iwp) and isinstance(c, iwp):
                    if self.prior < c.prior:
                        c.parenthesis = True
                c.__c__(writer)

        writer.write(self.suffix)
        if self.parenthesis:
            writer.write(")")


class OpDeclare(Operator):

    def __init__(self, *variables):

        super(OpDeclare, self).__init__(*variables)
        self.delim = ",@s"

    def __c__(self, writer):
        child = self.children[0]
        if isinstance(child, OpAssign):
            v = child.children[0]
            if not isinstance(v, Variable):
                raise TypeError(
                    "Wrong child type: expected Variable"
                )
        elif isinstance(child, Variable):
            v = child
        else:
            raise TypeError(
                "Wrong child type: expected Variable or OpAssign"
            )

        if v.static:
            writer.write("static ")
        if v.const:
            writer.write("const ")

        v_type = v.type
        p_count = " "
        while isinstance(v_type, Pointer):
            v_type = v_type.type
            p_count += "*"
        writer.write(v_type.name + p_count)
        child.__c__(writer)

        for child in self.children[1:]:
            if isinstance(child, OpAssign):
                v = child.children[0]
                if not isinstance(v, Variable):
                    raise TypeError(
                        "Wrong child type: expected Variable"
                    )
            elif isinstance(child, Variable):
                v = child
            else:
                raise TypeError(
                    "Wrong child type: expected Variable or OpAssign"
                )

            p_count = ""
            t = v.type
            while isinstance(t, Pointer):
                t = t.type
                p_count += "*"

            if t is not v_type:
                raise TypeError(
                    "All variable in OpDeclare must have the same type"
                )

            writer.write(self.delim + p_count)
            child.__c__(writer)


class OpIndex(Operator):

    def __init__(self, var, index):
        super(OpIndex, self).__init__(var, index)
        self.delim = "["
        self.suffix = "]"


class OpSDeref(Operator):

    def __init__(self, struct_var, field):
        super(OpSDeref, self).__init__(struct_var)

        delim = "."
        if isinstance(struct_var, Variable):
            if isinstance(struct_var.type, Pointer):
                delim = "->"
        self.field = field
        self.suffix = delim + field


class OpCall(Operator):

    __type_references__ = ("children", "type")

    def __init__(self, func, *args):
        super(OpCall, self).__init__(*args)

        self.type = None
        self.delim = ",@s"
        self.suffix = ")"

        if isinstance(func, str):
            t = Type.lookup(func)
            self.prefix = t.name + "(@a"
        elif isinstance(func, Variable):
            # Pointer to the function
            t = func
            self.prefix = t.name + "(@a"
        elif isinstance(func, OpSDeref):
            t = func.children[0]
            while isinstance(func, OpSDeref):
                t = t.children[0]
            self.prefix = t.name + func.delim + str(func.field) + "(@a"
        else:
            raise ValueError(
                "Invalid type of func in OpCall: {}".format(type(func))
            )

        self.type = t


class OpMCall(Operator):

    __type_references__ = ("children", "type")

    def __init__(self, macro, *args):
        super(OpMCall, self).__init__(*args)
        self.type = Type.lookup(macro)
        if len(args) > 0:
            self.prefix = self.type.name + "("
            # slashless line breaking is allowed for macro
            self.delim = ",@s"
            self.suffix = ")"
        else:
            self.prefix = self.type.name
            self.delim = ""
            self.suffix = ""


class OpStrConcat(Operator):

    def __init__(self, *args):
        super(OpStrConcat, self).__init__(*args)


class OpBreak(Operator):

    def __init__(self):
        super(OpBreak, self).__init__()
        self.prefix = "break"


class OpRet(Operator):

    def __init__(self, arg = None):
        super(OpRet, self).__init__(arg)
        if arg:
            self.prefix = "return" + "@b"
        else:
            self.prefix = "return"


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


class OpCast(UnaryOperator):

    __type_references__ = ("children", "type")

    def __init__(self, type, arg):
        super(OpCast, self).__init__("(" + self.type.name + ")", arg)
        self.type = Type.lookup(type)


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

    def __init__(self, arg1, arg2, comb_op, parenthesis = False):
        super(OpCombAssign, self).__init__(comb_op.op_str + "=",
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


op_priority = {
    OpIndex:      1,
    OpSDeref:     1,
    OpDec:        1,
    OpInc:        1,
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
