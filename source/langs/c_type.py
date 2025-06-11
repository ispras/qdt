__all__ = [
    "CTypeSpecifier"
  , "CTypeQualifier"
  , "CSpecQualList"
]

from .c_words import (
    CWords,
)


class CTypeSpecifier(CWords):

    # Sourced productions

    @staticmethod
    def s_type_specifier__base(BASE_TYPE_SPECIFIER):
        return dict(
            name = BASE_TYPE_SPECIFIER,
            base = True,
        )

    @staticmethod
    def s_type_specifier__typedef_name(IDENTIFIER):
        # Note that, `typedef_name: identifier` only
        return dict(
            name = IDENTIFIER,
            base = False,
        )

    # Extensions to other productions

    @staticmethod
    def s_declaration_specifier__type(type_specifier):
        return type_specifier


class CTypeQualifier(CWords):

    # Sourced productions

    @staticmethod
    def s_type_qualifier(TYPE_QUALIFIER):
        return TYPE_QUALIFIER

    # Extensions to other productions

    @staticmethod
    def s_specifier_qualifier_item__type(type_specifier):
        return type_specifier

    @staticmethod
    def s_specifier_qualifier_item__type_qualifier(type_qualifier):
        return type_qualifier

    @staticmethod
    def s_declaration_specifier__type_qualifier(type_qualifier):
        return type_qualifier


class CSpecQualList:
    "User must define `specifier_qualifier_item` production."

    @staticmethod
    def s_specifier_qualifier_list(specifier_qualifier_item):
        return [specifier_qualifier_item]

    @staticmethod
    def s_specifier_qualifier_list__n(
        specifier_qualifier_list, specifier_qualifier_item
    ):
        return specifier_qualifier_list + [specifier_qualifier_item]


class CAtomic(CWords):

    # Extensions to other productions

    @staticmethod
    def s_type_qualifier__atomic(ATOMIC):
        return ATOMIC

    @staticmethod
    def s_type_specifier__atomic(ATOMIC, LPAREN, type_name, RPAREN):
        raise NotImplementedError(ATOMIC + "(%s)" % type_name)
