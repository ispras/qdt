__all__ = [
    "CDeclSpec"
  , "CAlignSpecExts"
]


from .c_punct import (
    CPunctuation,
)
from .c_words import (
    CWords,
)


class CDeclSpec(CWords):
    """ This sub-grammar defines self-sufficient productions only.
See: CDeclSpecEx.
    """

    @staticmethod
    def s_declaration_specifiers(declaration_specifier):
        return [declaration_specifier]

    @staticmethod
    def s_declaration_specifiers__n(
        declaration_specifiers, declaration_specifier
    ):
        return declaration_specifiers + [declaration_specifier]

    # --

    @staticmethod
    def s_declaration_specifier__storage_class(STORAGE_CLASS_SPECIFIER):
        return STORAGE_CLASS_SPECIFIER

    @staticmethod
    def s_declaration_specifier__function(FUNCTION_SPECIFIER):
        return FUNCTION_SPECIFIER


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
