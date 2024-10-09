__all__ = [
    "CDeclSpec"
      , "CDeclSpecEx"
]


from .c_punct import (
    CPunctuation,
)
from .c_type import (
    CTypeSimple,
)


class CDeclSpec(CTypeSimple, CPunctuation):
    """ This sub-grammar defines self-sufficient productions only.
See: CDeclSpecEx.
    """

    @staticmethod
    def p_declaration_specifiers(declaration_specifier):
        return [declaration_specifier]

    @staticmethod
    def p_declaration_specifiers__n(
        declaration_specifiers, declaration_specifier
    ):
        return declaration_specifiers + [declaration_specifier]

    # --

    @staticmethod
    def p_declaration_specifier__storage_class(STORAGE_CLASS_SPECIFIER):
        return STORAGE_CLASS_SPECIFIER

    @staticmethod
    def p_declaration_specifier__type(type_specifier):
        return type_specifier

    @staticmethod
    def p_declaration_specifier__type_qualifier(type_qualifier):
        return type_qualifier

    @staticmethod
    def p_declaration_specifier__function(FUNCTION_SPECIFIER):
        return FUNCTION_SPECIFIER



class CDeclSpecEx(CDeclSpec):
    """ This grammar extends CDeclSpec with productions which require external
productions/tokens to be defined...
    - constant_expression
    - declarator
    - static_assert_declaration
    - type_name
    - ??? (it's not finished yet)
    """

    @staticmethod
    def p_declaration_specifier__alignment(alignment_specifier):
        return alignment_specifier

    # --

    @staticmethod
    def p_alignment_specifier__by_type(ALIGN_AS, LPAREN, type_name, RPAREN):
        raise NotImplementedError(ALIGN_AS + "(%s)" % type_name)

    @staticmethod
    def p_alignment_specifier__by_const(
        ALIGN_AS, LPAREN, constant_expression, RPAREN
    ):
        raise NotImplementedError(ALIGN_AS + "(constant_expression)")

    # --

    @staticmethod
    def p_enumerator__manual(IDENTIFIER, ASSIGN, constant_expression):
        # Note:
        #    enumerator : enumeration_constant ASSIGN constant_expression
        #    but
        #    enumeration_constant: identifier
        #    only
        raise NotImplementedError(IDENTIFIER + " = [value] as `enum` item")

    # --

    @staticmethod
    def p_struct_or_union_specifier__anon(
            struct_or_union, struct_declaration_block
    ):
        raise NotImplementedError("struct/union { ... }")

    @staticmethod
    def p_struct_or_union_specifier__full(
            struct_or_union, IDENTIFIER, struct_declaration_block
    ):
        raise NotImplementedError(
            "struct/union " + IDENTIFIER + " { ... }"
        )

    # --

    @staticmethod
    def p_struct_declaration_block(
        LPAREN, struct_declaration_list, RPAREN
    ):
        return struct_declaration_list

    # ..

    @staticmethod
    def p_struct_declaration_list(struct_declaration):
        return [struct_declaration]

    @staticmethod
    def p_struct_declaration_list__n(
        struct_declaration_list, struct_declaration,
    ):
        return struct_declaration_list + [struct_declaration]

    # --

    # TODO: struct_declaration: static_assert_declaration
    # TODO: struct_declaration:
    #       specifier_qualifier_list struct_declarator_list SEMI
    # TODO: struct_declaration:
    #       specifier_qualifier_list SEMI

    # --

    @staticmethod
    def p_struct_declarator_list(struct_declarator):
        return [struct_declarator]

    @staticmethod
    def p_struct_declarator_list__n(
        struct_declarator_list, COMMA, struct_declarator
    ):
        return struct_declarator_list + [struct_declarator]

    # --

    # TODO: struct_declarator: declarator
    # TODO: struct_declarator: COLON constant_expression
    # TODO: struct_declarator: declarator COLON constant_expression

    # --

    @staticmethod
    def p_type_specifier__atomic(ATOMIC, LPAREN, type_name, RPAREN):
        raise NotImplementedError(ATOMIC + "(%s)" % type_name)


    @staticmethod
    def p_specifier_qualifier_item__alignment(alignment_specifier):
        return alignment_specifier
