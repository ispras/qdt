__all__ = [
    "CDeclaration"
      , "CDecl"
]


from .c_decl_spec import (
    CDeclSpec,
)
from .c_type import (
    CTypeSpecifier,
    CTypeQualifier,
    CSpecQualList,
)
from ..late import (
    Late,
)
from ..model import (
    Function,
    Pointer,
    Type,
    TypeNotRegistered,
)
from ..short_ply_grammar import (
    short_ply_grammar,
)


spec_and_name = set([
    "short",
    "long",
    "unsigned",
    "signed",
])

class CDeclaration(
    CDeclSpec,
    CTypeSpecifier,
    CTypeQualifier,
    CSpecQualList
):
    t_STAR = r"\*"

    @staticmethod
    def p_declaration(declaration_specifiers__0, declaration_specifiers__1):
        # Declaration mast have at least two tokens.
        # Else, it can be confused with a an expression.
        # So, the production requires two lists of specifiers.
        # That's insignificantly how the parser do split specifiers.
        declaration_specifiers = (
            declaration_specifiers__0 + declaration_specifiers__1
        )

        # TODO: Currently, it's only possible to be a variable.
        #       Normally, struct/enum/typedef must also get here.

        # That's a variable.
        # Last specifier is actually the variable name.
        # I.e. it's like a direct_declarator.
        # So, emulate this.
        direct_declarator = dict(declaration_specifiers[-1])
        direct_declarator["type"] = str

        return list(iter_declarations(
            declaration_specifiers[:-1],
            [([direct_declarator], None)]
        ))

    @staticmethod
    def p_declaration__init(declaration_specifiers, init_declarator_list):
        return list(iter_declarations(
            declaration_specifiers,
            init_declarator_list
        ))

    @staticmethod
    def p_declaration__init_2(
        declaration_specifiers__0,
        declaration_specifiers__1,
        init_declarator_list
    ):
        # Declarations like `short int a, b` are not covered by both
        # `p_declaration__init` because there are two `declaration_specifiers`
        # lists, and `p_declaration` because it does not consumes COMMA inside
        # init_declarator_list.
        return list(iter_declarations(
            declaration_specifiers__0 + declaration_specifiers__1,
            init_declarator_list
        ))

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
        return next(iter_declarations(
            declaration_specifiers, ((declarator, None),)
        ))

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
    def _p_direct_declarator__parenthesed(
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
            # This results in `... old_style_function_decl()`
            args = (),
        )

    @staticmethod
    def p_direct_declarator__func_void_args(
        direct_declarator, LPAREN, IDENTIFIER, RPAREN
    ):
        if IDENTIFIER != "void":
            raise SyntaxError("void is expected")
        return dict(
            type = Function,
            name = direct_declarator,
            # This results in `... new_style_function_decl(void)`
            args = None,
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

    # --

    @staticmethod
    def p_type_name(specifier_qualifier_list):
        return get_type(specifier_qualifier_list, [])

    @staticmethod
    def p_type_name__abstract(specifier_qualifier_list, abstract_declarator):
        return get_type(specifier_qualifier_list, abstract_declarator)

    # --

    @staticmethod
    def p_abstract_declarator__pointer(pointer):
        return pointer

    # TODO
    @staticmethod
    def _p_abstract_declarator__direct(direct_abstract_declarator):
        return [direct_abstract_declarator]

    # TODO
    @staticmethod
    def _p_abstract_declarator__p_direct(pointer, direct_abstract_declarator):
        return pointer + [direct_abstract_declarator]


@short_ply_grammar(
    debugfile = True,
    start = "declaration",
)
class CDecl(CDeclaration):

    @staticmethod
    def t_WS(t):
        r"[ \t]"

    @staticmethod
    def p_error(p):
        raise SyntaxError

    @staticmethod
    def t_error(t):
        raise SyntaxError


def iter_declarations(declaration_specifiers, init_declarator_list):
    var_type = None

    for declarator, initializer in init_declarator_list:
        if initializer is not None:
            raise NotImplementedError

        pointers = declarator[:-1]
        direct_declarator = declarator[-1]

        dd_type = direct_declarator["type"]

        if dd_type is Function:
            kw = {}

            ret_type_ds = []

            for ds in declaration_specifiers:
                if ds in ("static",) + CDeclSpec.FUNCTION_SPECIFIERS:
                    kw[ds] = True
                else:
                    ret_type_ds.append(ds)

            if var_type is None:
                decl_spec_type = get_declaration_type(ret_type_ds)
                var_type = make_pointer(decl_spec_type, pointers)

            name_desc = direct_declarator["name"]
            assert name_desc["type"] is str

            yield Function(
                name = name_desc["name"],
                args = direct_declarator["args"],
                ret_type = var_type,
                **kw
            )
        elif dd_type is str:
            # variable
            if var_type is None:
                decl_spec_type = get_declaration_type(declaration_specifiers)
                var_type = make_pointer(decl_spec_type, pointers)

            name = direct_declarator["name"]
            assert isinstance(name, str)
            yield var_type(name)
        else:
            raise NotImplementedError


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


def get_type(specifier_qualifier_list, abstract_declarator):
    # specifier_qualifier_list is subset of declaration_specifiers
    base_type = get_declaration_type(specifier_qualifier_list)
    # XXX: current impementation allows only pointers in abstract_declarator
    return make_pointer(base_type, abstract_declarator)
