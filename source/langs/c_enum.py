__all__ = [
    "CEnum"
]

from .c_punct import (
    CPunctuation,
)
from .c_words import (
    CWords,
)
from ..model import (
    Enumeration,
    Type,
)


class CEnum(CPunctuation, CWords):

    # Sourced productions

    @staticmethod
    def s_enum_specifier__ref(ENUM, IDENTIFIER):
        res = Type[IDENTIFIER]
        assert isinstance(res, Enumeration)
        return res

    @staticmethod
    def s_enum_specifier__anon(ENUM, enumerator_list_block):
        return Enumeration(enumerator_list_block)

    @staticmethod
    def s_enum_specifier__full(ENUM, IDENTIFIER, enumerator_list_block):
        return Enumeration(enumerator_list_block, enum_name = IDENTIFIER)

    # --

    @staticmethod
    def s_enumerator_list_block(LBRACE, enumerator_list, RBRACE):
        return enumerator_list

    @staticmethod
    def s_enumerator_list_block__comma(LBRACE, enumerator_list, COMMA, RBRACE):
        return enumerator_list

    # --

    @staticmethod
    def s_enumerator_list(enumerator):
        return [enumerator]

    @staticmethod
    def s_enumerator_list__n(enumerator_list, COMMA, enumerator):
        return enumerator_list + [enumerator]

    # --

    @staticmethod
    def s_enumerator__auto(IDENTIFIER):
        # Note:
        #    enumerator : enumeration_constant
        #    but
        #    enumeration_constant: identifier
        #    only
        return IDENTIFIER

    # Extensions to other productions

    @staticmethod
    def s_type_specifier__enum(enum_specifier):
        return dict(
            name = enum_specifier.name if enum_specifier.is_named
                   else None,
            type = CEnum,
        )
