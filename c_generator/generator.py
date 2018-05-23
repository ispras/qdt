__all__ = [
    "Function"
    , "Const"
    , "OpDeclare"
    , "OpIndex"
    , "OpSDeref"
    , "OpAssign"
    , "OpCombAssign"
    , "OpBreak"
    , "OpRet"
    , "OpAddr"
    , "OpDeref"
    , "OpAdd"
    , "OpSub"
    , "OpMul"
    , "OpDiv"
    , "OpRem"
    , "OpAnd"
    , "OpOr"
    , "OpXor"
    , "OpNot"
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
    , "OpCall"
    , "OpMCall"
    , "Goto"
    , "MacroBranch"
    , "LoopWhile"
    , "LoopDoWhile"
    , "LoopFor"
    , "BranchIf"
    , "BranchElse"
    , "BranchSwitch"
    , "SwitchCase"
    , "Cast"
    , "Comment"
]

from source import (
    Type,
    Pointer,
    Variable
)

TAB_SIZE = 4

indent_level = 0

class Node(object):
    # traverse order indicator for `ObjectVisitor`
    __descend__ = ("children",)

    def __init__(self, parent = None):
        self.children = []
        self.parent = parent

        self.local_vars = set()

        self.do_indent = True
        self.ending = ";"

    def add_child(self, child):
        self.children.append(child)
        child.set_parent(self)

    def set_parent(self, parent):
        self.parent = parent

    @staticmethod
    def indent(writer):
        writer.write(" " * TAB_SIZE * indent_level)

    def out_children(self, writer, it = None):
        global indent_level
        indent_level += 1
        for child in (self.children if it is None else it):
            Node.out(child, writer)
        indent_level -= 1

    @staticmethod
    def out(node, writer):
        if not isinstance(node.parent, Operator):
            if node.do_indent:
                Node.indent(writer)
        node.out(writer)
        if not isinstance(node.parent, Operator):
            if node.ending != "":
                if node.ending == "}":
                    Node.indent(writer)
                writer.write(node.ending + "\n")
        return


class Function(Node):
    def __init__(self, name):
        Node.__init__(self)
        self.name = name

    def out(self, writer):
        self.out_children(writer)


class Const(Node):
    def __init__(self, val):
        Node.__init__(self)
        self.val = str(val)
        self.do_indent = False
        self.ending = ""

    def __str__(self):
        return self.val

    def out(self, writer):
        writer.write(self.val)


class VariableUsage(Node):
    def __init__(self, var):
        Node.__init__(self)
        self.var = var
        self.do_indent = False
        self.ending = ""

    def get_var(self):
        return self.var

    def out(self, writer):
        writer.write(self.var.name)
        if self.var.array_size is not None and self.parent is not None:
            if isinstance(self.parent, OpDeclare):
                writer.write("[%d]" % self.var.array_size)

class Operator(Node):
    def __init__(self, *args, **kw_args):
        Node.__init__(self)
        self.ending = ";"

        self.prefix = ""
        self.delim = ""
        self.suffix = ""

        try:
            self.parenthesis = kw_args["parenthesis"]
        except KeyError:
            self.parenthesis = False

        try:
            self.prior = op_priority[type(self)]
        except KeyError:
            self.prior = 0

        for arg in args:
            if isinstance(arg, Node):
                self.add_child(arg)
            elif isinstance(arg, Variable):
                self.add_child(VariableUsage(arg))

    def set_parent(self, parent):
        if (isinstance(self, OpDeclare) or isinstance(self, OpAssign)) \
                and parent is not None:
            child = self.children[0]
            while not isinstance(child, VariableUsage) \
                    and not isinstance(child, Const):
                if len(child.children) < 1:
                    break
                child = child.children[0]
            else:
                if isinstance(child, VariableUsage):
                    parent.local_vars.add(child.var)
        Node.set_parent(self, parent)

    def out(self, writer):
        writer.write(self.prefix)

        need_parenthesis = self.parenthesis
        if not need_parenthesis:
            try:
                need_parenthesis = self.prior > self.parent.prior\
                                   and self.prior and self.parent.prior
            except AttributeError:
                need_parenthesis = False

        if need_parenthesis:
            writer.write("(")

        if isinstance(self, OpRet) and len(self.children) > 0:
            writer.write(" ")

        if self.children:
            l = iter(self.children)
            Node.out(next(l), writer)
            for ch in l:
                writer.write(self.delim)
                Node.out(ch, writer)
        writer.write(self.suffix)
        if need_parenthesis:
            writer.write(")")


class OpDeclare(Operator):
    def __init__(self, *variables):
        Operator.__init__(self, *variables)

    def out(self, writer):
        child = self.children[0]
        # now there's no support for generation of expressions like
        # int a = x, b = y;
        # only
        #   int a = x;
        # or
        #   int a, b; ...
        # are supported
        # that's why all the children must have the same type
        if isinstance(child, VariableUsage):
            assert(len(set([var.var.type for var in self.children])) == 1)
            if child.var.static:
                writer.write("static ")
            v_tp = child.var.type
            writer.write(v_tp.name + " ")
            if self.children:
                l = iter(self.children)
                next(l).out(writer)
                for arg in l:
                    writer.write(", ")
                    arg.out(writer)
        elif isinstance(child, Operator):
            assert(len(self.children) == 1)
            assert(isinstance(child, OpAssign))

            writer.write(child.children[0].var.type.name + " ")
            child.out(writer)
        else:
            raise TypeError(
                "Wrong operators combination: "
                "expected declare and assignment"
            )


class OpIndex(Operator):
    def __init__(self, var, index):
        Operator.__init__(self, var, index)
        self.delim = "["
        self.suffix = "]"


class OpSDeref(Operator):
    def __init__(self, struct_var, field):
        Operator.__init__(self, struct_var, field)
        self.field = field
        self.delim = "."
        t = None
        if isinstance(struct_var, Variable):
            t = struct_var.type
        if t is not None and isinstance(t, Pointer):
            self.delim = "->"

    def get_var(self):
        return self.children[0].var


class NAryOperator(Operator):
    def __init__(self, argc, op_str, *args, **kw_args):
        Operator.__init__(self, *args, **kw_args)
        # ternary operator is not supported
        assert(len(args) == argc and argc < 3)
        self.op_str = op_str
        self.argc = argc

        self.prefix = self.op_str
        self.delim = "@s"


class UnaryOperator(NAryOperator):
    def __init__(self, op_str, arg1):
        NAryOperator.__init__(self, 1, op_str, arg1)


class BinaryOperator(NAryOperator):
    def __init__(self, op_str, arg1, arg2, parenthesis):
        NAryOperator.__init__(self, 2, op_str, arg1, arg2, parenthesis = parenthesis)
        self.prefix = ""
        self.delim = "@s" + op_str + "@b"


class OpAssign(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "=", arg1, arg2, parenthesis)


class OpCombAssign(BinaryOperator):
    def __init__(self, arg1, arg2, comb_op, parenthesis = False):
        BinaryOperator.__init__(self, comb_op.op_str + "=", arg1, arg2, parenthesis)


class OpBreak(NAryOperator):
    def __init__(self):
        NAryOperator.__init__(self, 0, "break")


class OpRet(NAryOperator):
    def __init__(self, *arg):
        # zero or one argument is supported
        assert(len(arg) <= 1)
        NAryOperator.__init__(self, len(arg), "return", *arg)


class OpAddr(UnaryOperator):
    def __init__(self, arg1):
        UnaryOperator.__init__(self, "&", arg1)


class OpDeref(UnaryOperator):
    def __init__(self, arg1):
        UnaryOperator.__init__(self, "*", arg1)

    def get_var(self):
        return self.children[0].var


class OpAdd(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "+", arg1, arg2, parenthesis)


class OpSub(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "-", arg1, arg2, parenthesis)


class OpMul(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "*", arg1, arg2, parenthesis)


class OpDiv(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "/", arg1, arg2, parenthesis)


class OpRem(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "%", arg1, arg2, parenthesis)


class OpAnd(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "&", arg1, arg2, parenthesis)


class OpOr(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "|", arg1, arg2, parenthesis)


class OpXor(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "^", arg1, arg2, parenthesis)


class OpNot(UnaryOperator):
    def __init__(self, arg1):
        UnaryOperator.__init__(self, "~", arg1)


class OpLShift(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "<<", arg1, arg2, parenthesis)


class OpRShift(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, ">>", arg1, arg2, parenthesis)


class OpLogAnd(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "&&", arg1, arg2, parenthesis)


class OpLogOr(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "||", arg1, arg2, parenthesis)


class OpLogNot(UnaryOperator):
    def __init__(self, arg1):
        UnaryOperator.__init__(self, "!", arg1)


class OpEq(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "==", arg1, arg2, parenthesis)


class OpNEq(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "!=", arg1, arg2, parenthesis)


class OpGE(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, ">=", arg1, arg2, parenthesis)


class OpLE(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "<=", arg1, arg2, parenthesis)


class OpGreater(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, ">", arg1, arg2, parenthesis)


class OpLower(BinaryOperator):
    def __init__(self, arg1, arg2, parenthesis = False):
        BinaryOperator.__init__(self, "<", arg1, arg2, parenthesis)


class OpCall(Operator):
    def __init__(self, func, *args, **kw_args):
        Operator.__init__(self, *args)
        implicit_decl = False
        if isinstance(func, str):
            try:
                implicit_decl = kw_args["implicit_decl"]
            except KeyError:
                pass
            if not implicit_decl:
                self.func = Type.lookup(func)
        elif isinstance(func, Variable):
            if isinstance(func, Variable):
                self.func = func
            else:
                raise TypeError
        elif isinstance(func, OpSDeref):
            func = func.get_var().name + func.delim + str(func.field)
            implicit_decl = True
        else:
            raise TypeError

        if implicit_decl:
            self.prefix = func + "("
        else:
            self.prefix = self.func.name + "("

        self.delim = ",@s"
        self.suffix = ")"


class OpMCall(Operator):
    def __init__(self, macro, *args):
        Operator.__init__(self, *args)
        self.macro = Type.lookup(macro)
        if len(args) > 0:
            self.prefix = self.macro.name + "("
            self.delim = ",@s" # slashless line breaking is allowed for macro
            self.suffix = ")"
        else:
            self.prefix = self.macro.name
            self.delim = ""
            self.suffix = ""

class Goto(Node):
    def __init__(self, lable):
        Node.__init__(self)
        self.keyword = "goto " + lable

    def out(self, writer):
        writer.write(self.keyword)

class Branch(Node):
    def __init__(self, *cond_parts, **kw):
        Node.__init__(self)

        pre = kw.get("pre", True)
        self.pre = pre

        if pre:
            self.ending = "}"
        else:
            self.ending = ";"
        self.conds = []

        for c in cond_parts:
            if isinstance(c, Variable):
                self.conds.append(VariableUsage(c))
            else:
                self.conds.append(c)

        self.conds_delim = ";"
        self.keyword = ""

    def out(self, writer):
        writer.write(self.keyword)

        if self.pre:
            writer.write(" (")
            if self.conds:
                l = iter(self.conds)
                next(l).out(writer)
                for c in l:
                    writer.write(self.conds_delim + " ")
                    c.out(writer)
            writer.write(") {\n")
        else:
            writer.write(" {\n")
        self.out_children(writer)

        # there is only 1 post-cond branch - do-while loop
        if not self.pre:
            self.indent(writer)
            writer.write("} while (")
            if self.conds:
                l = iter(self.conds)
                next(l).out(writer)
                for c in l:
                    writer.write(self.conds_delim + " ")
                    c.out(writer)
            writer.write(")")


# It's describes construction like
# MACRO(x, y) { ... }
class MacroBranch(Node):
    def __init__(self, macro):
        Node.__init__(self)
        self.macro = macro
        self.ending = "}"

    def out(self, writer):
        self.macro.out(writer)

        writer.write(" {\n")
        self.out_children(writer)


class LoopWhile(Branch):
    def __init__(self, cond):
        Branch.__init__(self, cond)
        self.keyword = "while"


class LoopDoWhile(Branch):
    def __init__(self, cond):
        Branch.__init__(self, cond, pre = False)
        self.keyword = "do"


class LoopFor(Branch):
    def __init__(self, iter_var, start, end_cond, step):
        Branch.__init__(self,
                        OpAssign(iter_var, Const(start)),
                        end_cond,
                        OpAssign(iter_var, OpAdd(iter_var, Const(step))))
        self.keyword = "for"

class BranchIf(Branch):
    def __init__(self, cond):
        Branch.__init__(self, cond)
        self.keyword = "if"
        self.ending = "}"

        self.else_blocks = []

    def add_else(self, else_bl):
        self.else_blocks.append(else_bl)

    def out(self, writer):
        l = len(self.else_blocks)
        if l > 0:
            # ending is the keyword of next else block
            # or "}"
            self.ending = ""
        super(BranchIf, self).out(writer)

        i = 0
        while i < l - 1:
            self.else_blocks[i].out(writer)
            i += 1

        if i < l:
            # it's the last else block
            self.else_blocks[i].out(writer)
            self.indent(writer)
            writer.write("}\n")

# Don't add this class as child to any Nodes
# It's should be added only by `add_else`
# ending str is written in BranchIf out
class BranchElse(Node):
    def __init__(self, cond = None):
        Node.__init__(self)
        if cond is not None:
            self.keyword = "} else if"
        else:
            self.keyword = "} else"

        self.cond = cond

    def out(self, writer):
        self.indent(writer)
        writer.write(self.keyword)

        if self.cond is not None:
            writer.write(" (")
            self.cond.out(writer)
            writer.write(") {\n")
        else:
            writer.write(" {\n")
        self.out_children(writer)

class BranchSwitch(Branch):
    def __init__(self,
                 cond_var,
                 add_breaks = True,
                 cases = [],
                 child_ident = False
        ):
        Branch.__init__(self, cond_var)
        assert(len(cases) > 0)
        self.keyword = "switch"
        self.cases = cases
        self.bodies = {}
        self.child_ident = child_ident
        for case in self.cases:
            child = SwitchCase(case, add_breaks)
            self.bodies[str(child)] = child
            self.add_child(child)
        child = SwitchCase(Const("default"), add_breaks)
        self.bodies[str(child)] = child
        self.add_child(child)
        self.ending = "}"

    def out_children(self, writer, it = None):
        global indent_level
        if self.child_ident:
            indent_level += 1
        for child in (self.children if it is None else it):
            Node.out(child, writer)
        if self.child_ident:
            indent_level -= 1

class SwitchCase(Node):
    def __init__(self, case, add_break, *args):
        if isinstance(case, Variable):
            case = VariableUsage(case)
        Node.__init__(self, case, *args)
        self.has_break = add_break
        self.case = case

        self.add_child(self.case)
        self.ending = "}"

    def __str__(self):
        return str(self.case)

    def out(self, writer):
        if self.has_break:
            self.add_child(OpBreak())

        has_nontriv_children = len(self.children) > 1
        if not has_nontriv_children:
            self.ending = ""

        if str(self.case) != "default":
            writer.write("case ")
        if self.children:
            l = iter(self.children)
            next(l).out(writer)
            writer.write(":" + (" {" if has_nontriv_children else "") + "\n")
            self.out_children(writer, l)


class Cast(Operator):
    def __init__(self, t, arg):
        Operator.__init__(self, arg)
        self.t = Type.lookup(t)

    def out(self, writer):
        writer.write("(")
        writer.write(self.t.name)
        writer.write(")")
        self.out_children(writer)


class Comment(Node):
    def __init__(self, value):
        Node.__init__(self)
        self.value = value
        self.do_indent = True
        self.ending = ""

    def out(self, writer):
        writer.write("/* ")
        writer.write(self.value)
        writer.write(" */\n")

op_priority = {
    OpIndex:    1,
    OpSDeref:   1,
    OpDeref:    2,
    OpNot:      2,
    OpLogNot:   2,
    OpMul:      3,
    OpDiv:      3,
    OpRem:      3,
    OpAdd:      4,
    OpSub:      4,
    OpLShift:   5,
    OpRShift:   5,
    OpGE:       6,
    OpLE:       6,
    OpGreater:  6,
    OpLower:    6,
    OpEq:       7,
    OpNEq:      7,
    OpAddr:     8,
    OpAnd:      8,
    OpXor:      9,
    OpOr:       10,
    OpLogAnd:   11,
    OpLogOr:    12,
    OpAssign:   14,
}
