__all__ = [
    "CConstToks",
    "CConst",
]


from ..c_const import (
    CINT,
)

class CConstToks:

    @staticmethod
    def t_INTEGER(t):
        # This is coarse. CINT must parse accurately.
        "((0[xX][0-9a-fA-F]+)|([0-9]+))[uUlL]*"
        return t

    @staticmethod
    def t_FLOAT(t):
        "\
((\
(0[xX])\
(\
((([0-9a-fA-F]+[.])|([0-9a-fA-F]*[.][0-9a-fA-F]+))([eEpP][+-]?[0-9]+)?)\
|\
([0-9a-fA-F]+[eEpP][+-]?[0-9]+)\
)\
)|(\
((([0-9][0-9a-fA-F]*[.])|(\
([0-9][0-9a-fA-F]*)?[.][0-9][0-9a-fA-F]*\
))([eEpP][+-]?[0-9]+)?)\
|\
([0-9][0-9a-fA-F]*[eEpP][+-]?[0-9]+)\
))\
[fFlL]?\
"
        return t

    @staticmethod
    def t_CHAR(t):
        "'[^']+'"
        return t

    @staticmethod
    def t_STR(t):
        '"[^"]*"'
        return t


class CConst(CConstToks):

    @staticmethod
    def p_constant__int(INTEGER):
        return CINT(INTEGER)

    @staticmethod
    def p_constant__float(FLOAT):
        raise NotImplementedError("float constant")

    @staticmethod
    def p_constant__char(CHAR):
        raise NotImplementedError("character constant")

    # Note, according to C standard, STR (string-litheral) is used by
    # multiple productions...
    #     primary_expression: STR | constant
    #     static_assert-declaration: ... (..., STR)
    # I.e. STR is not constant only.
