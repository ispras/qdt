__all__ = [
    "CStructOrUnion"
  , "CTypeSpecifier"
  , "CTypeQualifier"
  , "CSpecQualList"
]

from .c_decl_helpers import (
    iter_sturct_fields,
)
from .c_punct import (
    CPunctuation,
)
from .c_words import (
    CWords,
)
from ..model import (
    Structure,
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


class CStructOrUnion(CPunctuation, CWords):
    """ User must define
    - constant_expression
    - declarator
    - specifier_qualifier_list
    """

    # Sourced productions

    @staticmethod
    def s_struct_or_union__struct(STRUCT):
        return Structure

    @staticmethod
    def s_struct_or_union__union(UNION):
        raise NotImplementedError(UNION)

    # --

    @staticmethod
    def s_struct_or_union_specifier__ref(struct_or_union, IDENTIFIER):
        ret = Type[IDENTIFIER]
        assert isinstance(ret, struct_or_union)
        return ret

    @staticmethod
    def s_struct_or_union_specifier__anon(
            struct_or_union, struct_declaration_block
    ):
        return struct_or_union(None,
            *iter_sturct_fields(struct_declaration_block)
        )

    @staticmethod
    def s_struct_or_union_specifier__full(
            struct_or_union, IDENTIFIER, struct_declaration_block
    ):
        return struct_or_union(IDENTIFIER,
            *iter_sturct_fields(struct_declaration_block)
        )

    # --

    @staticmethod
    def s_struct_declaration_block(
        LBRACE, struct_declaration_list, RBRACE
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

    @staticmethod
    def s_struct_declaration__last_spec_is_declarator(
        specifier_qualifier_list,
        SEMI
    ):
        return (
            specifier_qualifier_list[:-1],
            [ # init_declarator_list
                [
                    [
                        dict(
                            type = str,
                            **specifier_qualifier_list[-1]
                        )
                    ], # declarator
                    None,  # initializer
                ],
            ]
        )

    @staticmethod
    def s_struct_declaration(
        specifier_qualifier_list,
        struct_declarator_list,
        SEMI
    ):
        return (specifier_qualifier_list, struct_declarator_list)

    # Note, in configuration...
    #    specifier_qualifier_item . IDENTIFIER
    # The state machine cannot distinguish those rules...
    #    1. direct_declarator -> IDENTIFIER
    #    2. type_specifier -> IDENTIFIER
    # The former results in reducing IDENTIFIER to struct_declarator and
    # leads to configuration...
    #     specifier_qualifier_list . struct_declarator_list
    # The letter results in reducing IDENTIFIER to specifier_qualifier_item and
    # leads to configuration...
    #     specifier_qualifier_list .
    # I.e. it cannot distinguish two productions above.
    # The production above forces it to wait for either COMMA or SEMI to make
    # a choice.
    # Note that, in the original C parsing chain there is a type table.
    # The lexer chooses between IDENTIFIER and TYPE_IDENTIFIER tokens
    # querying the table.
    # Lexically, those tokens matches same regular expression.
    # And the rule 2. looks like...
    #    2. type_specifier -> TYPE_IDENTIFIER

    @staticmethod
    def s_struct_declaration__last_spec_is_first_declarator(
        specifier_qualifier_list,
        COMMA,
        struct_declarator_list,
        SEMI
    ):
        return (
            specifier_qualifier_list[:-1],
            [ # init_declarator_list
                [
                    [
                        dict(
                            type = str,
                            **specifier_qualifier_list[-1]
                        )
                    ], # declarator
                    None,  # initializer
                ],
            ] + struct_declarator_list
        )

    # --

    @staticmethod
    def s_struct_declarator(declarator):
        return (declarator, None)

    @staticmethod
    def s_struct_declarator__bitfield(declarator, COLON, constant_expression):
        return (declarator, constant_expression)

    # TODO
    @staticmethod
    def _s_struct_declarator__anon_bitfield(COLON, constant_expression):
        return (None, constant_expression)

    # Extensions to other productions

    @staticmethod
    def s_type_specifier__struct_or_union(struct_or_union_specifier):
        return struct_or_union_specifier
