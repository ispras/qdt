__all__ = [
    "CStructOrUnion"
  , "CTypeSpecifier"
  , "CTypeQualifier"
  , "CSpecQualList"
]

from .c_words import (
    CWords,
)


class CTypeSpecifier(CWords):

    # Sourced productions

    @staticmethod
    def p_type_specifier__base(BASE_TYPE_SPECIFIER):
        return dict(
            name = BASE_TYPE_SPECIFIER,
            base = True,
        )

    @staticmethod
    def p_type_specifier__typedef_name(IDENTIFIER):
        # Note that, `typedef_name: identifier` only
        return dict(
            name = IDENTIFIER,
            base = False,
        )

    # Extensions to other productions

    @staticmethod
    def p_specifier_qualifier_item__type_qualifier(type_qualifier):
        return type_qualifier

    @staticmethod
    def p_declaration_specifier__type(type_specifier):
        return type_specifier


class CTypeQualifier(CWords):

    # Sourced productions

    @staticmethod
    def p_type_qualifier(TYPE_QUALIFIER):
        return TYPE_QUALIFIER

    # Extensions to other productions

    @staticmethod
    def p_specifier_qualifier_item__type(type_specifier):
        return type_specifier

    @staticmethod
    def p_declaration_specifier__type_qualifier(type_qualifier):
        return type_qualifier


class CSpecQualList:
    "User must define `specifier_qualifier_item` production."

    @staticmethod
    def p_specifier_qualifier_list(specifier_qualifier_item):
        return [specifier_qualifier_item]

    @staticmethod
    def p_specifier_qualifier_list__n(
        specifier_qualifier_item, specifier_qualifier_list
    ):
        return [specifier_qualifier_item] + specifier_qualifier_list


class CAtomic(CWords):

    # Extensions to other productions

    @staticmethod
    def p_type_qualifier__atomic(ATOMIC):
        return ATOMIC

    @staticmethod
    def p_type_specifier__atomic(ATOMIC, LPAREN, type_name, RPAREN):
        raise NotImplementedError(ATOMIC + "(%s)" % type_name)


class CEnum(CWords):

    # Sourced productions

    @staticmethod
    def p_enum_specifier__ref(ENUM, IDENTIFIER):
        raise NotImplementedError("enum " + IDENTIFIER)

    @staticmethod
    def p_enum_specifier__anon(ENUM, enumerator_list_block):
        raise NotImplementedError("enum { ... }")

    @staticmethod
    def p_enum_specifier__full(ENUM, IDENTIFIER, enumerator_list_block):
        raise NotImplementedError(
            "struct/union " + IDENTIFIER + " { ... }"
        )

    # --

    @staticmethod
    def p_enumerator_list_block(LBRACE, enumerator_list, RBRACE):
        return enumerator_list

    @staticmethod
    def p_enumerator_list_block__comma(LBRACE, enumerator_list, COMMA, RBRACE):
        return enumerator_list

    # --

    @staticmethod
    def p_enumerator_list(enumerator):
        return [enumerator]

    @staticmethod
    def p_enumerator_list__n(enumerator_list, COMMA, enumerator):
        return enumerator_list + [enumerator]

    # --

    @staticmethod
    def p_enumerator__auto(IDENTIFIER):
        # Note:
        #    enumerator : enumeration_constant
        #    but
        #    enumeration_constant: identifier
        #    only
        raise NotImplementedError(IDENTIFIER + " as `enum` item")

    # Extensions to other productions

    @staticmethod
    def p_type_specifier__enum(enum_specifier):
        return enum_specifier


class CStructOrUnion(CWords):

    @staticmethod
    def p_type_specifier__struct_or_union(struct_or_union_specifier):
        raise NotImplementedError("struct/union ID_opt {...}_opt")

    # --

    @staticmethod
    def p_struct_or_union_specifier__ref(struct_or_union, IDENTIFIER):
        raise NotImplementedError("struct/union " + IDENTIFIER)

    # --

    @staticmethod
    def p_struct_or_union__struct(STRUCT):
        raise NotImplementedError(STRUCT)

    @staticmethod
    def p_struct_or_union__union(UNION):
        raise NotImplementedError(UNION)

