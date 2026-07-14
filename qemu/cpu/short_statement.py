# TODO: rename to "short block item" (module, related classes, etc..)

from source.function.tree import (
    BinaryOperator,
    BranchElse,
    CaseRange,
    Declare,
    LoopFor,
    OpDeclareAssign,
    Return,
    SwitchCaseDefault,
)
from source.langs.c_decl import (
    CDeclarationAndExpr,
)
from source.model import (
    NodeVisitor,
    Variable,
)
from source.short_ply_grammar import (
    short_ply_grammar,
)


class Define(BinaryOperator):

    prior = 0
    op_str = ":="

    @property
    def name(self):
        return self.children[0]

    @property
    def value(self):
        return self.children[1]


class DefineFinder(NodeVisitor):

    def __init__(self, *a, **kw):
        super(DefineFinder, self).__init__(*a, **kw)
        self.defines = []

    def __visit__(self, cur):
        if isinstance(cur, Define):
            self.defines.append(cur)


@short_ply_grammar(
    debugfile = True,
    start = "block_item",
)
class ShortStatement(CDeclarationAndExpr):

    t_DEFINE = ":="

    @staticmethod
    def t_WS(t):
        r"[ \t]"

    @staticmethod
    def s_block_item__stmnt(statement):
        return statement

    @staticmethod
    def s_block_item__decl(declaration):
        for decl in declaration:
            if not isinstance(decl, (Variable, OpDeclareAssign)):
                raise SyntaxError(
                    "Only variable declaration is alowed inside block"
                )

        return Declare(*declaration)

    @staticmethod
    def s_statement__expr(expression):
        return expression

    @staticmethod
    def s_statement__else(ELSE):
        return BranchElse()

    @staticmethod
    def s_statement__elif(ELSE, expression):
        return BranchElse(expression)

    @staticmethod
    def s_statement__for(FOR, expression):
        return LoopFor(step = expression)

    @staticmethod
    def s_statement__for_no_expr(FOR):
        return LoopFor()

    @staticmethod
    def s_statement__return(RETURN):
        return Return()

    @staticmethod
    def s_statement__return_expr(RETURN, expression):
        return Return(expression)

    @staticmethod
    def s_primary_expression__define(identifier, DEFINE, primary_expression):
        return Define(identifier, primary_expression)

    @staticmethod
    def s_statement__default(DEFAULT):
        return SwitchCaseDefault()

    # This is GCC extension.
    # This is not a statement but it will be handled as `case` range by
    # misc/short_inst.py/MergeContext.merge_statements.
    @staticmethod
    def s_statement__case_range(
        constant_expression__l,
        DOTS,
        constant_expression__r
    ):
        return CaseRange(constant_expression__l, constant_expression__r)

    @staticmethod
    def t_error(t):
        raise SyntaxError

    @staticmethod
    def p_error(p):
        raise SyntaxError
