# TODO: rename to "short block item" (module, related classes, etc..)

from source.function.tree import (
    BinaryOperator,
    BranchElse,
    Declare,
    LoopFor,
    Return,
)
from source.langs.c_decl import (
    CDeclaration,
)
from source.langs.c_expr import (
    CExpr,
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
class ShortStatement(
    CDeclaration,
    CExpr,
):

    t_DEFINE = ":="

    @staticmethod
    def t_WS(t):
        r"[ \t]"

    @staticmethod
    def p_block_item__stmnt(statement):
        return statement

    @staticmethod
    def p_block_item__decl(declaration):
        for decl in declaration:
            if not isinstance(decl, Variable):
                raise SyntaxError(
                    "Only variable declaration is alowed inside block"
                )
            if decl.initializer is not None:
                # TODO: convert to OpDeclareAssign?
                raise NotImplementedError
        return Declare(*declaration)

    @staticmethod
    def p_statement__expr(expression):
        return expression

    @staticmethod
    def p_statement__else(ELSE):
        return BranchElse()

    @staticmethod
    def p_statement__elif(ELSE, expression):
        return BranchElse(expression)

    @staticmethod
    def p_statement__for(FOR, expression):
        return LoopFor(step = expression)

    @staticmethod
    def p_statement__for_no_expr(FOR):
        return LoopFor()

    @staticmethod
    def p_statement__return(RETURN):
        return Return()

    @staticmethod
    def p_statement__return_expr(RETURN, expression):
        return Return(expression)

    @staticmethod
    def p_primary_expression__define(identifier, DEFINE, primary_expression):
        return Define(identifier, primary_expression)

    @staticmethod
    def t_error(t):
        raise SyntaxError

    @staticmethod
    def p_error(p):
        raise SyntaxError
