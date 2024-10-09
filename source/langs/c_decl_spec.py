__all__ = [
    "CDeclSpec"
      , "CDeclSpecEx"
]


from .c_punct import (
    CPunctuation,
)
from .c_words import (
    CWords,
)


class CDeclSpec(CWords, CPunctuation):
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
    def p_specifier_qualifier_item__alignment(alignment_specifier):
        return alignment_specifier
