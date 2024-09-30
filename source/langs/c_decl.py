__all__ = [
    "CDecl"
]


from .c_words import (
    CWords,
)
from ..late import (
    Late,
)
from ..model import (
    Enumeration,
    Function,
    Pointer,
    Type,
    TypeNotRegistered,
    Variable,
)
from ..short_ply_grammar import (
    short_ply_grammar,
)


one_of = lambda words : "((" + ")|(".join(words) + "))(?=[ \t])"

def word(*words):
    def decorate(func):
        func.__doc__ = one_of(words)
        return func
    return decorate


spec_and_name = set([
    "short",
    "long",
    "unsigned",
    "signed",
])

@short_ply_grammar(
    debugfile = True,
)
class CDecl(CWords):
    t_DOTS = r"\.\.\."

    t_STAR = r"\*"

    t_LPAREN = r"\("
    t_RPAREN = r"\)"

    t_LBRACE = r"\{"
    t_RBRACE = r"\}"

    t_COMMA = ","

    @staticmethod
    def t_WS(t):
        r"[ \t]"

    @staticmethod
    def p_declaration(declaration_specifiers):
        raise NotImplementedError

    @staticmethod
    def p_declaration__init(declaration_specifiers, init_declarator_list):
        if len(init_declarator_list) > 1:
            raise NotImplementedError

        declarator, initializer = init_declarator_list[0]
        if initializer is not None:
            raise NotImplementedError

        direct_declorator = declarator[-1]
        pointers = declarator[:-1]

        dd_type = direct_declorator["type"]

        if dd_type is Function:
            ret_type = get_declaration_type(declaration_specifiers)
            ret_type = make_pointer(ret_type, pointers)

            name_desc = direct_declorator["name"]
            assert name_desc["type"] is str

            return Function(
                name = name_desc["name"],
                args = direct_declorator["args"],
                ret_type = ret_type,
            )
        else:
            raise NotImplementedError

    # TODO: declaration: static_assert_declaration

    @staticmethod
    def p_init_declarator_list(init_declarator):
        return [init_declarator]

    @staticmethod
    def p_init_declarator_list__n(
        init_declarator_list, COMMA, init_declarator
    ):
        return init_declarator_list + [init_declarator]

    @staticmethod
    def p_init_declarator(declarator):
        return (declarator, None)

    # TODO
    @staticmethod
    def _p_init_declarator__with_init(declarator, ASSIGN, initializer):
        pass

    @staticmethod
    def p_direct_declarator__func_with_args(
        direct_declarator, LPAREN, parameter_type_list, RPAREN
    ):
        return dict(
            type = Function,
            name = direct_declarator,
            args = parameter_type_list,
        )

    @staticmethod
    def p_parameter_type_list(parameter_list):
        return parameter_list

    @staticmethod
    def p_parameter_type_list__va_arg(parameter_list, COMMA, DOTS):
        return parameter_list + [DOTS]

    @staticmethod
    def p_parameter_list(parameter_declaration):
        return [parameter_declaration]

    @staticmethod
    def p_parameter_list__n(parameter_list, COMMA, parameter_declaration):
        return parameter_list + [parameter_declaration]

    @staticmethod
    def p_parameter_declaration(declaration_specifiers, declarator):
        direct_declorator = declarator[-1]

        dd_type = direct_declorator["type"]
        if dd_type is not str:
            raise ValueError("argument name expected")

        pointers = declarator[:-1]

        var_type = get_declaration_type(declaration_specifiers)
        var_type = make_pointer(var_type, pointers)

        name = direct_declorator["name"]

        return Variable(name, var_type)

    @staticmethod
    def p_declaration_specifiers(declaration_specifier):
        return [declaration_specifier]

    @staticmethod
    def p_declaration_specifiers__n(
        declaration_specifiers, declaration_specifier
    ):
        return declaration_specifiers + [declaration_specifier]

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

    # TODO:
    # alignment-specifier:
    #    ALIGN_AS ( type-name )
    #    ALIGN_AS ( constant-expression )
    @staticmethod
    def _p_declaration_specifier__alignment(alignment_specifier):
        return alignment_specifier

    @staticmethod
    def p_type_qualifier(TYPE_QUALIFIER):
        return TYPE_QUALIFIER

    @staticmethod
    def p_type_qualifier__atomic(ATOMIC):
        return ATOMIC

    @staticmethod
    def p_type_specifier__base(BASE_TYPE_SPECIFIER):
        return dict(
            type = Type,
            name = BASE_TYPE_SPECIFIER,
            base = True,
        )

    # TODO
    @staticmethod
    def _p_type_specifier__atomic(ATOMIC, LPAREN, type_name, RPAREN):
        pass

    # TODO
    @staticmethod
    def _p_type_specifier__struct_or_union():
        pass

    @staticmethod
    def p_type_specifier__enum(enum_specifier):
        return enum_specifier

    @staticmethod
    def p_type_specifier__typedef_name(IDENTIFIER):
        # Note that, `typedef_name: identifier` only
        return dict(
            type = Type,
            name = IDENTIFIER,
            base = False,
        )

    @staticmethod
    def p_declarator(direct_declarator):
        return [direct_declarator]

    @staticmethod
    def p_declarator__pointer(pointer, direct_declarator):
        return pointer + [direct_declarator]

    @staticmethod
    def p_direct_declarator__identifier(IDENTIFIER):
        return dict(
            type = str,
            name = IDENTIFIER,
        )

    @staticmethod
    def _p_direct_declarator__paranthized(
        LPAREN, declarator, RPAREN
    ):
        raise NotImplementedError

    @staticmethod
    def p_direct_declarator__func_without_args(
        direct_declarator, LPAREN, RPAREN
    ):
        return dict(
            type = Function,
            name = direct_declarator,
            args = (),
        )

    @staticmethod
    def p_pointer__qualified(STAR, type_qualifier_list):
        return [type_qualifier_list]

    @staticmethod
    def p_pointer__qualified_n(STAR, type_qualifier_list, pointer):
        return [type_qualifier_list] + pointer

    @staticmethod
    def p_pointer(STAR):
        return [[]]

    @staticmethod
    def p_pointer__n(STAR, pointer):
        return [[]] + pointer

    @staticmethod
    def p_type_qualifier_list(type_qualifier):
        return [type_qualifier]

    @staticmethod
    def p_type_qualifier_list__n(type_qualifier_list, type_qualifier):
        return type_qualifier_list + [type_qualifier]

    @staticmethod
    def p_enum_specifier(ENUM, IDENTIFIER):
        return dict(
            type = Enumeration,
            name = IDENTIFIER,
            items = None,
        )

    @staticmethod
    def p_enum_specifier__anonimous(ENUM, enumerator_list_block):
        return dict(
            type = Enumeration,
            name = None,
            items = enumerator_list_block,
        )

    @staticmethod
    def p_enum_specifier__definition(ENUM, IDENTIFIER, enumerator_list_block):
        return dict(
            type = Enumeration,
            name = IDENTIFIER,
            items = enumerator_list_block,
        )

    @staticmethod
    def p_enumerator_list_block(LBRACE, enumerator_list, RBRACE):
        return enumerator_list

    @staticmethod
    def p_enumerator_list_block__comma(LBRACE, enumerator_list, COMMA, RBRACE):
        return enumerator_list

    @staticmethod
    def p_enumerator_list(enumerator):
        return [enumerator]

    @staticmethod
    def p_enumerator_list__n(enumerator_list, COMMA, enumerator):
        return enumerator_list + [enumerator]

    @staticmethod
    def p_enumerator__auto(IDENTIFIER):
        # Note that, `enumeration_constant: identifier` only
        return IDENTIFIER

    @staticmethod
    def _p_enumerator__manual(IDENTIFIER, ASSIGN, constant_expression):
        # Note that, `enumeration_constant: identifier` only
        return (IDENTIFIER, constant_expression)

    """

    @staticmethod
    def p_type_name(specifier_qualifier_list):
        return specifier_qualifier_list

    # TODO
    @staticmethod
    def _p_type_name__abstract(specifier_qualifier_list, abstract_declarator):
        raise NotImplementedError

    @staticmethod
    def p_specifier_qualifier_list(specifier_qualifier_item):
        return [specifier_qualifier_item]

    @staticmethod
    def p_specifier_qualifier_list__n(
        specifier_qualifier_item, specifier_qualifier_list
    ):
        return [specifier_qualifier_item] + specifier_qualifier_list

    @staticmethod
    def p_specifier_qualifier_item__type(type_specifier):
        return type_specifier

    @staticmethod
    def p_specifier_qualifier_item__type_qualifier(type_qualifier):
        return type_qualifier

    # TODO
    @staticmethod
    def _p_specifier_qualifier_item__alignment(alignment_specifier):
        return alignment_specifier

    """

    @staticmethod
    def p_error(p):
        raise SyntaxError


def get_declaration_type(declaration_specifiers):
    type_info = None
    specs = []
    for spec in declaration_specifiers:
        if isinstance(spec, str):
            specs.append(spec)
        else:
            if type_info is None:
                type_info = spec
            else:
                if type_info["name"] in spec_and_name:
                    # E.g. unsigned int, signed long long
                    specs.append(type_info["name"])
                    type_info = spec
                else:
                    # E.g. `int int` or `int short`
                    raise ValueError(
                        "multiple types: %s, %s" % (type_info, spec)
                    )
    if type_info is None:
        raise ValueError("no type name found")

    specs.append(type_info["name"])

    spec_type_name = " ".join(specs)

    try:
        return Type[spec_type_name]
    except TypeNotRegistered:
        if type_info["base"]:
            return Type(
                name = spec_type_name,
                base = True,
                incomplete = type_info["name"] == "void",
            )
        else:
            return Late(spec_type_name)


def make_pointer(base_type, pointers):
    for pointer_qualifiers in pointers:
        base_type = Pointer(base_type,
            **dict((q, True) for q in pointer_qualifiers)
        )
    return base_type
