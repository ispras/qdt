__all__ = [
    "CExpr"
]

from .c_const import (
    CConstant,
)
from .c_op import (
    COp,
)
from .c_punct import (
    CPunctuation,
)
from .c_words import (
    CWords,
)

from source.c_const import (
    CSTR,
)
from source.function.tree import (
    Call,
    OpAdd,
    OpAddr,
    OpAnd,
    OpAssign,
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
from source.late import (
    K_FUNC,
    Late,
)


class CExpr(
    CConstant,
    COp,
    CPunctuation,
    CWords,
):

    @staticmethod
    def s_identifier(IDENTIFIER):
        return Late(IDENTIFIER)

    @staticmethod
    def s_primary_expression__id(identifier):
        return identifier

    @staticmethod
    def s_primary_expression__const(constant):
        return constant

    @staticmethod
    def s_primary_expression__str(STR):
        # strip "
        return CSTR(STR[1:-1])

    @staticmethod
    def s_primary_expression__paren(LPAREN, expression, RPAREN):
        expression.parenthesis = True
        return expression

    # TODO : primary_expression : generic-selection

    @staticmethod
    def s_postfix_expression(primary_expression):
        return primary_expression

    @staticmethod
    def s_postfix_expression__index(
        postfix_expression, LBRACKET, expression, RBRACKET
    ):
        return OpIndex(postfix_expression, expression)

    @staticmethod
    def s_postfix_expression__call(
        postfix_expression, LPAREN, argument_expression_list, RPAREN
    ):
        if isinstance(postfix_expression, Late):
            postfix_expression.specify(K_FUNC)
        return Call(postfix_expression, *argument_expression_list)

    @staticmethod
    def s_argument_expression_list(assignment_expression):
        return [assignment_expression]

    @staticmethod
    def s_argument_expression_list__n(
        argument_expression_list, COMMA, assignment_expression
    ):
        return argument_expression_list + [assignment_expression]

    @staticmethod
    def s_postfix_expression__call_no_args(
        postfix_expression, LPAREN, RPAREN
    ):
        return Call(postfix_expression)

    @staticmethod
    def s_postfix_expression__struct_deref(
        postfix_expression, DOT, IDENTIFIER
    ):
        return OpSDeref(postfix_expression, IDENTIFIER)

    @staticmethod
    def s_postfix_expression__struct_ptr_deref(
        postfix_expression, RARROW, IDENTIFIER
    ):
        return OpSDeref(postfix_expression, IDENTIFIER)

    @staticmethod
    def s_postfix_expression__post_inc(postfix_expression, INC):
        return OpPostInc(postfix_expression)

    @staticmethod
    def s_postfix_expression__post_dec(postfix_expression, DEC):
        return OpPostDec(postfix_expression)

    # TODO: postfix_expression : ( type-name ) { initializer-list }
    # TODO: postfix_expression : ( type-name ) { initializer-list , }

    @staticmethod
    def s_unary_expression(postfix_expression):
        return postfix_expression

    @staticmethod
    def s_unary_expression__pre_inc(INC, unary_expression):
        return OpPreInc(unary_expression)

    @staticmethod
    def s_unary_expression__pre_dec(DEC, unary_expression):
        return OpPreDec(unary_expression)

    @staticmethod
    def s_unary_expression__un_op(unary_operator, cast_expression):
        return unary_operator(cast_expression)

    @staticmethod
    def s_unary_operator__addr(BIT_AND):
        return OpAddr

    @staticmethod
    def s_unary_operator__ptr_deref(STAR):
        return OpDeref

    @staticmethod
    def s_unary_operator__unary_plus(PLUS):
        return OpPlus

    @staticmethod
    def s_unary_operator__unary_minus(MINUS):
        return OpMinus

    @staticmethod
    def s_unary_operator__bit_not(TILDE):
        return OpNot

    @staticmethod
    def s_unary_operator__logical_not(LOG_NOT):
        return OpLogNot

    @staticmethod
    def s_unary_expression__sizeof_expr(SIZEOF, unary_expression):
        return OpSizeOf(unary_expression)

    # TODO: unary-expression: _Alignof ( type-name )

    @staticmethod
    def s_cast_expression(unary_expression):
        return unary_expression

    @staticmethod
    def s_multiplicative_expression(cast_expression):
        return cast_expression

    @staticmethod
    def s_multiplicative_expression__mul(
        multiplicative_expression, STAR, cast_expression
    ):
        return OpMul(multiplicative_expression, cast_expression)

    @staticmethod
    def s_multiplicative_expression__div(
        multiplicative_expression, SLASH, cast_expression
    ):
        return OpDiv(multiplicative_expression, cast_expression)

    @staticmethod
    def s_multiplicative_expression__rem(
        multiplicative_expression, PERCENT, cast_expression
    ):
        return OpRem(multiplicative_expression, cast_expression)

    @staticmethod
    def s_additive_expression(multiplicative_expression):
        return multiplicative_expression

    @staticmethod
    def s_additive_expression__sum(
        additive_expression, PLUS, multiplicative_expression
    ):
        return OpAdd(additive_expression, multiplicative_expression)

    @staticmethod
    def s_additive_expression__sub(
        additive_expression, MINUS, multiplicative_expression
    ):
        return OpSub(additive_expression, multiplicative_expression)

    @staticmethod
    def s_shift_expression(additive_expression):
        return additive_expression

    @staticmethod
    def s_shift_expression__left(
        shift_expression, LSHIFT, additive_expression
    ):
        return OpLShift(shift_expression, additive_expression)

    @staticmethod
    def s_shift_expression__right(
        shift_expression, RSHIFT, additive_expression
    ):
        return OpRShift(shift_expression, additive_expression)

    @staticmethod
    def s_relational_expression(shift_expression):
        return shift_expression

    @staticmethod
    def s_relational_expression__lt(
        relational_expression, LT, shift_expression
    ):
        return OpLess(relational_expression, shift_expression)

    @staticmethod
    def s_relational_expression__gt(
        relational_expression, GT, shift_expression
    ):
        return OpGreater(relational_expression, shift_expression)

    @staticmethod
    def s_relational_expression__le(
        relational_expression, LE, shift_expression
    ):
        return OpLE(relational_expression, shift_expression)

    @staticmethod
    def s_relational_expression__ge(
        relational_expression, GE, shift_expression
    ):
        return OpGE(relational_expression, shift_expression)

    @staticmethod
    def s_equality_expression(relational_expression):
        return relational_expression

    @staticmethod
    def s_equality_expression__eq(
        equality_expression, EQ, relational_expression
    ):
        return OpEq(equality_expression, relational_expression)

    @staticmethod
    def s_equality_expression__not_eq(
        equality_expression, NE, relational_expression
    ):
        return OpNEq(equality_expression, relational_expression)

    @staticmethod
    def s_bit_and_expression(equality_expression):
        return equality_expression

    @staticmethod
    def s_bit_and_expression__and(
        bit_and_expression, BIT_AND, equality_expression
    ):
        return OpAnd(bit_and_expression, equality_expression)

    @staticmethod
    def s_bit_xor_expression(bit_and_expression):
        return bit_and_expression

    @staticmethod
    def s_bit_xor_expression__xor(
        bit_xor_expression, BIT_XOR, bit_and_expression
    ):
        return OpXor(bit_xor_expression, bit_and_expression)

    @staticmethod
    def s_bit_or_expression(bit_xor_expression):
        return bit_xor_expression

    @staticmethod
    def s_bit_or_expression__xor(
        bit_or_expression, BIT_OR, bit_xor_expression
    ):
        return OpOr(bit_or_expression, bit_xor_expression)

    @staticmethod
    def s_logical_and_expression(bit_or_expression):
        return bit_or_expression

    @staticmethod
    def s_logical_and_expression__and(
        logical_and_expression, LOG_AND, bit_or_expression
    ):
        return OpLogAnd(logical_and_expression, bit_or_expression)

    @staticmethod
    def s_logical_or_expression(logical_and_expression):
        return logical_and_expression

    @staticmethod
    def s_logical_or_expression__or(
        logical_or_expression, LOG_OR, logical_and_expression
    ):
        return OpLogOr(logical_or_expression, logical_and_expression)

    @staticmethod
    def s_conditional_expression(logical_or_expression):
        return logical_or_expression

    @staticmethod
    def s_conditional_expression__ternary(
        logical_or_expression, QUEST, expression, COLON, conditional_expression
    ):
        return OpTernCond(
            logical_or_expression, expression, conditional_expression
        )

    @staticmethod
    def s_assignment_expression(conditional_expression):
        return conditional_expression

    @staticmethod
    def s_assignment_expression__assignment(
        unary_expression, assignment_operator, assignment_expression
    ):
        return assignment_operator(unary_expression, assignment_expression)

    @staticmethod
    def s_assignment_operator__asign(ASSIGN):
        return OpAssign

    @staticmethod
    def s_assignment_operator__comb(COMB_ASSIGN):
        return lambda a, b: OpCombAssign(a, b, COMB_ASSIGN[:-1])

    @staticmethod
    def s_expression(assignment_expression):
        return assignment_expression

    @staticmethod
    def s_expression__n(expression, COMMA, assignment_expression):
        raise NotImplementedError("comma separated expressions")

    # contributions

    @staticmethod
    def s_constant_expression(conditional_expression):
        return conditional_expression
