__all__ = [
    "CStructOrUnion"
  , "CEnum"
  , "CTypeSpecifier"
  , "CTypeQualifier"
  , "CSpecQualList"
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
    def s_specifier_qualifier_item__type_qualifier(type_qualifier):
        return type_qualifier

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
        return enum_specifier


class CStructOrUnion(CWords):
    """ User must defile
  - struct_declarator
  - struct_declaration
    """

    # Sourced productions

    @staticmethod
    def s_struct_or_union__struct(STRUCT):
        raise NotImplementedError(STRUCT)

    @staticmethod
    def s_struct_or_union__union(UNION):
        raise NotImplementedError(UNION)

    # --

    @staticmethod
    def s_struct_or_union_specifier__ref(struct_or_union, IDENTIFIER):
        raise NotImplementedError("struct/union " + IDENTIFIER)

    @staticmethod
    def s_struct_or_union_specifier__anon(
            struct_or_union, struct_declaration_block
    ):
        raise NotImplementedError("struct/union { ... }")

    @staticmethod
    def s_struct_or_union_specifier__full(
            struct_or_union, IDENTIFIER, struct_declaration_block
    ):
        raise NotImplementedError(
            "struct/union " + IDENTIFIER + " { ... }"
        )

    # --

    @staticmethod
    def s_struct_declaration_block(
        LPAREN, struct_declaration_list, RPAREN
    ):
        return struct_declaration_list

    # ..

    @staticmethod
    def s_struct_declaration_list(struct_declaration):
        return [struct_declaration]

    @staticmethod
    def s_struct_declaration_list__n(
        struct_declaration_list, struct_declaration,
    ):
        return struct_declaration_list + [struct_declaration]

    # --

    @staticmethod
    def s_struct_declarator_list(struct_declarator):
        return [struct_declarator]

    @staticmethod
    def s_struct_declarator_list__n(
        struct_declarator_list, COMMA, struct_declarator
    ):
        return struct_declarator_list + [struct_declarator]

    # --

    # TODO: struct_declaration: static_assert_declaration
    # TODO: struct_declaration:
    #       specifier_qualifier_list struct_declarator_list SEMI
    # TODO: struct_declaration:
    #       specifier_qualifier_list SEMI

    # --

    # TODO: struct_declarator: declarator
    # TODO: struct_declarator: COLON constant_expression
    # TODO: struct_declarator: declarator COLON constant_expression

    # Extensions to other productions

    @staticmethod
    def s_type_specifier__struct_or_union(struct_or_union_specifier):
        raise NotImplementedError("struct/union ID_opt {...}_opt")
