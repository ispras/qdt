# TODO: rename to "short block item" (module, related classes, etc..)

from source.c_const import (
    CSTR,
)
from source.function.tree import (
    BinaryOperator,
    BranchElse,
    Call,
    Declare,
    OpAdd,
    OpAddr,
    OpAnd,
    OpAssign,
    OpCast,
    OpCombAssign,
    OpDeref,
    OpDiv,
    OpEq,
    OpGE,
    OpGreater,
    OpIndex,
    OpLE,
    OpLess,
    OpLogAnd,
    OpLogOr,
    OpLogNot,
    OpLShift,
    OpMinus,
    OpMul,
    OpNEq,
    OpNot,
    OpOr,
    OpPlus,
    OpPostDec,
    OpPostInc,
    OpPreDec,
    OpPreInc,
    OpRem,
    OpRShift,
    OpSDeref,
    OpSizeOf,
    OpSub,
    OpTernCond,
    OpXor,
)
from source.langs.c_const import (
    CConstant,
)
from source.langs.c_punct import (
    CPunctuation,
)
from source.langs.c_words import (
    CWords,
)
from source.late import (
    K_ENUM,
    K_FUNC,
    K_STRUCT,
    K_TYPE,
    K_UNION,
    Late,
)
from source.model import (
    NodeVisitor,
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
class ShortStatement(CConstant, CPunctuation, CWords):

    t_RARROW = "->"

    t_DEC = "--"
    t_INC = r"\+\+"
    t_QUEST = r"\?"

    t_BIT_AND = "&"
    t_BIT_OR = r"\|"
    t_BIT_XOR = r"\^"
    t_LOG_AND = "&&"
    t_LOG_OR = r"\|\|"

    t_STAR = r"\*"
    t_PLUS = r"\+"

    t_MINUS = "-"
    t_TILDE = "~"
    t_LOG_NOT = "!"
    t_PERCENT = "%"
    t_SLASH = "/"
    t_LSHIFT = "<<"
    t_RSHIFT = ">>"

    t_LT = "<"
    t_GT = ">"
    t_LE = "<="
    t_GE = ">="
    t_EQ = "=="
    t_NE = "!="

    t_DEFINE = ":="

    t_ASSIGN = "="
    t_COMB_ASSIGN = r"(\*|\/|%|\+|-|(<<)|(>>)|&|\^|\|)="

    @staticmethod
    def t_WS(t):
        r"[ \t]"

    @staticmethod
    def p_block_item__stmnt(statement):
        return statement

    @staticmethod
    def p_block_item__decl(declaration):
        return declaration

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
    def p_declaration(identifier__t, identifier_list__n):
        identifier__t.specify(K_TYPE)
        vs = []
        for n in identifier_list__n:
            vs.append(identifier__t(n.name))
        return Declare(*vs)

    @staticmethod
    def p_identifier(IDENTIFIER):
        return Late(IDENTIFIER)

    @staticmethod
    def p_identifier__struct(STRUCT, identifier):
        identifier.specify(K_STRUCT)
        return identifier

    @staticmethod
    def p_identifier__union(UNION, identifier):
        identifier.specify(K_UNION)
        return identifier

    @staticmethod
    def p_identifier__enum(ENUM, identifier):
        identifier.specify(K_ENUM)
        return identifier

    @staticmethod
    def p_identifier_list(identifier):
        return [identifier]

    @staticmethod
    def p_identifier_list__n(identifier_list, COMMA, identifier):
        return identifier_list + [identifier]

    @staticmethod
    def p_primary_expression__id(identifier):
        return identifier

    @staticmethod
    def p_primary_expression__const(constant):
        return constant

    @staticmethod
    def p_primary_expression__str(STR):
        return CSTR(STR)

    @staticmethod
    def p_primary_expression__define(identifier, DEFINE, primary_expression):
        return Define(identifier, primary_expression)

    @staticmethod
    def p_primary_expression__paren(LPAREN, expression, RPAREN):
        expression.parenthesis = True
        return expression

    # TODO : primary_expression : generic-selection

    @staticmethod
    def p_postfix_expression(primary_expression):
        return primary_expression

    @staticmethod
    def p_postfix_expression__index(
        postfix_expression, LBRACKET, expression, RBRACKET
    ):
        return OpIndex(postfix_expression, expression)

    @staticmethod
    def p_postfix_expression__call(
        postfix_expression, LPAREN, argument_expression_list, RPAREN
    ):
        if isinstance(postfix_expression, Late):
            postfix_expression.specify(K_FUNC)
        return Call(postfix_expression, *argument_expression_list)

    @staticmethod
    def p_postfix_expression__call_no_args(
        postfix_expression, LPAREN, RPAREN
    ):
        return Call(postfix_expression)

    @staticmethod
    def p_postfix_expression__struct_deref(
        postfix_expression, DOT, IDENTIFIER
    ):
        return OpSDeref(postfix_expression, IDENTIFIER)

    @staticmethod
    def p_postfix_expression__struct_ptr_deref(
        postfix_expression, RARROW, IDENTIFIER
    ):
        return OpSDeref(postfix_expression, IDENTIFIER)

    @staticmethod
    def p_postfix_expression__post_inc(postfix_expression, INC):
        return OpPostInc(postfix_expression)

    @staticmethod
    def p_postfix_expression__post_dec(postfix_expression, DEC):
        return OpPostDec(postfix_expression)

    # TODO: postfix_expression : ( type-name ) { initializer-list }
    # TODO: postfix_expression : ( type-name ) { initializer-list , }

    @staticmethod
    def p_argument_expression_list(assignment_expression):
        return [assignment_expression]

    @staticmethod
    def p_argument_expression_list__n(
        argument_expression_list, COMMA, assignment_expression
    ):
        return argument_expression_list + [assignment_expression]

    @staticmethod
    def p_unary_expression(postfix_expression):
        return postfix_expression

    @staticmethod
    def p_unary_expression__pre_inc(INC, unary_expression):
        return OpPreInc(unary_expression)

    @staticmethod
    def p_unary_expression__pre_dec(DEC, unary_expression):
        return OpPreDec(unary_expression)

    @staticmethod
    def p_unary_expression__un_op(unary_operator, cast_expression):
        return unary_operator(cast_expression)

    @staticmethod
    def p_unary_operator__addr(BIT_AND):
        return OpAddr

    @staticmethod
    def p_unary_operator__ptr_deref(STAR):
        return OpDeref

    @staticmethod
    def p_unary_operator__unary_plus(PLUS):
        return OpPlus

    @staticmethod
    def p_unary_operator__unary_minus(MINUS):
        return OpMinus

    @staticmethod
    def p_unary_operator__bit_not(TILDE):
        return OpNot

    @staticmethod
    def p_unary_operator__logical_not(LOG_NOT):
        return OpLogNot

    @staticmethod
    def p_unary_expression__sizeof_expr(SIZEOF, unary_expression):
        return OpSizeOf(unary_expression)

    @staticmethod
    def p_unary_expression__sizeof_id(
        SIZEOF,
        LPAREN,
        identifier,  # type_name, actually
        RPAREN
    ):
        identifier.specify(K_TYPE)
        return OpSizeOf(identifier)

    # TODO: unary-expression: _Alignof ( type-name )

    @staticmethod
    def p_cast_expression(unary_expression):
        return unary_expression

    @staticmethod
    def p_cast_expression__cast_id(
        LPAREN,
        identifier,  # type_name, actually
        RPAREN,
        cast_expression
    ):
        identifier.specify(K_TYPE)
        return OpCast(identifier, cast_expression)

    @staticmethod
    def p_multiplicative_expression(cast_expression):
        return cast_expression

    @staticmethod
    def p_multiplicative_expression__mul(
        multiplicative_expression, STAR, cast_expression
    ):
        return OpMul(multiplicative_expression, cast_expression)

    @staticmethod
    def p_multiplicative_expression__div(
        multiplicative_expression, SLASH, cast_expression
    ):
        return OpDiv(multiplicative_expression, cast_expression)

    @staticmethod
    def p_multiplicative_expression__rem(
        multiplicative_expression, PERCENT, cast_expression
    ):
        return OpRem(multiplicative_expression, cast_expression)

    @staticmethod
    def p_additive_expression(multiplicative_expression):
        return multiplicative_expression

    @staticmethod
    def p_additive_expression__sum(
        additive_expression, PLUS, multiplicative_expression
    ):
        return OpAdd(additive_expression, multiplicative_expression)

    @staticmethod
    def p_additive_expression__sub(
        additive_expression, MINUS, multiplicative_expression
    ):
        return OpSub(additive_expression, multiplicative_expression)

    @staticmethod
    def p_shift_expression(additive_expression):
        return additive_expression

    @staticmethod
    def p_shift_expression__left(
        shift_expression, LSHIFT, additive_expression
    ):
        return OpLShift(shift_expression, additive_expression)

    @staticmethod
    def p_shift_expression__right(
        shift_expression, RSHIFT, additive_expression
    ):
        return OpRShift(shift_expression, additive_expression)

    @staticmethod
    def p_relational_expression(shift_expression):
        return shift_expression

    @staticmethod
    def p_relational_expression__lt(
        relational_expression, LT, shift_expression
    ):
        return OpLess(relational_expression, shift_expression)

    @staticmethod
    def p_relational_expression__gt(
        relational_expression, GT, shift_expression
    ):
        return OpGreater(relational_expression, shift_expression)

    @staticmethod
    def p_relational_expression__le(
        relational_expression, LE, shift_expression
    ):
        return OpLE(relational_expression, shift_expression)

    @staticmethod
    def p_relational_expression__ge(
        relational_expression, GE, shift_expression
    ):
        return OpGE(relational_expression, shift_expression)

    @staticmethod
    def p_equality_expression(relational_expression):
        return relational_expression

    @staticmethod
    def p_equality_expression__eq(
        equality_expression, EQ, relational_expression
    ):
        return OpEq(equality_expression, relational_expression)

    @staticmethod
    def p_equality_expression__not_eq(
        equality_expression, NE, relational_expression
    ):
        return OpNEq(equality_expression, relational_expression)

    @staticmethod
    def p_bit_and_expression(equality_expression):
        return equality_expression

    @staticmethod
    def p_bit_and_expression__and(
        bit_and_expression, BIT_AND, equality_expression
    ):
        return OpAnd(bit_and_expression, equality_expression)

    @staticmethod
    def p_bit_xor_expression(bit_and_expression):
        return bit_and_expression

    @staticmethod
    def p_bit_xor_expression__xor(
        bit_xor_expression, BIT_XOR, bit_and_expression
    ):
        return OpXor(bit_xor_expression, bit_and_expression)

    @staticmethod
    def p_bit_or_expression(bit_xor_expression):
        return bit_xor_expression

    @staticmethod
    def p_bit_or_expression__xor(
        bit_or_expression, BIT_OR, bit_xor_expression
    ):
        return OpOr(bit_or_expression, bit_xor_expression)

    @staticmethod
    def p_logical_and_expression(bit_or_expression):
        return bit_or_expression

    @staticmethod
    def p_logical_and_expression__and(
        logical_and_expression, LOG_AND, bit_or_expression
    ):
        return OpLogAnd(logical_and_expression, bit_or_expression)

    @staticmethod
    def p_logical_or_expression(logical_and_expression):
        return logical_and_expression

    @staticmethod
    def p_logical_or_expression__or(
        logical_or_expression, LOG_OR, logical_and_expression
    ):
        return OpLogOr(logical_or_expression, logical_and_expression)

    @staticmethod
    def p_conditional_expression(logical_or_expression):
        return logical_or_expression

    @staticmethod
    def p_conditional_expression__ternary(
        logical_or_expression, QUEST, expression, COLON, conditional_expression
    ):
        return OpTernCond(
            logical_or_expression, expression, conditional_expression
        )

    @staticmethod
    def p_assignment_expression(conditional_expression):
        return conditional_expression

    @staticmethod
    def p_assignment_expression__assignment(
        unary_expression, assignment_operator, assignment_expression
    ):
        return assignment_operator(unary_expression, assignment_expression)

    @staticmethod
    def p_assignment_operator__asign(ASSIGN):
        return OpAssign

    @staticmethod
    def p_assignment_operator__comb(COMB_ASSIGN):
        return lambda a, b: OpCombAssign(a, b, COMB_ASSIGN[:-1])

    @staticmethod
    def p_expression(assignment_expression):
        return assignment_expression

    @staticmethod
    def p_expression__n(expression, COMMA, assignment_expression):
        raise NotImplementedError("comma separated expressions")

    @staticmethod
    def p_error(p):
        raise SyntaxError
