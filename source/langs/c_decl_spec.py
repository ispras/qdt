__all__ = [
    "CDeclSpec"
  , "CFuncAndStSpec"
  , "CAlignSpecExts"
]


from .c_punct import (
    CPunctuation,
)
from .c_words import (
    CWords,
)


class CDeclSpec:
    """`declaration_specifier` production is required"""

    @staticmethod
    def s_declaration_specifiers(declaration_specifier):
        return [declaration_specifier]

    @staticmethod
    def s_declaration_specifiers__n(
        declaration_specifiers, declaration_specifier
    ):
        return declaration_specifiers + [declaration_specifier]


class CFuncAndStSpec(CWords):

    # Extensions to other productions

    @staticmethod
    def s_declaration_specifier__storage_class(STORAGE_CLASS_SPECIFIER):
        return dict(
            name = STORAGE_CLASS_SPECIFIER,
            type = CFuncAndStSpec,
        )

    @staticmethod
    def s_declaration_specifier__function(FUNCTION_SPECIFIER):
        return dict(
            name = FUNCTION_SPECIFIER,
            type = CFuncAndStSpec,
        )


class CAlignSpecExts(CWords, CPunctuation):
    "User must provide `alignment_specifier`"

    # Extensions to other productions

    @staticmethod
    def s_specifier_qualifier_item__alignment(alignment_specifier):
        return alignment_specifier

    @staticmethod
    def s_declaration_specifier__alignment(alignment_specifier):
        return alignment_specifier

    # TODO: move to `type_name` extensions
    @staticmethod
    def _s_alignment_specifier__by_type(ALIGN_AS, LPAREN, type_name, RPAREN):
        raise NotImplementedError(ALIGN_AS + "(%s)" % type_name)

    # TODO: move to `constant_expression` extensions
    @staticmethod
    def _s_alignment_specifier__by_const(
        ALIGN_AS, LPAREN, constant_expression, RPAREN
    ):
        raise NotImplementedError(ALIGN_AS + "(constant_expression)")
