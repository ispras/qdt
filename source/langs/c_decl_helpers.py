__all__ = [] # currently, direct import only

from .c_decl_spec import (
    CDeclSpec,
)
from .c_type import (
    CTypeQualifier,
)
from ..function.tree import (
    OpDeclareAssign,
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

from itertools import (
    chain,
    starmap,
)

spec_and_name = set([
    "short",
    "long",
    "unsigned",
    "signed",
])


def iter_sturct_fields(struct_declaration_block):
    for decl in chain(*starmap(iter_declarations, struct_declaration_block)):
        if isinstance(decl, OpDeclareAssign):
            # a bitfield
            var, bits = decl.children
            var.initializer = bits
            decl = var
        yield decl


def iter_declarations(declaration_specifiers, init_declarator_list):
    var_type = None

    for declarator, initializer in init_declarator_list:
        pointers = declarator[:-1]
        direct_declarator = declarator[-1]

        dd_type = direct_declarator["type"]

        if dd_type is Function:
            if initializer is not None:
                raise SyntaxError("initializer to a function")

            kw = {}

            ret_type_ds = []

            for ds in declaration_specifiers:
                if ds["type"] is CDeclSpec:
                    kw[ds["name"]] = True
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
            var = var_type(name)
            if initializer is None:
                yield var
            else:
                yield OpDeclareAssign(var, initializer)
        else:
            raise NotImplementedError

def get_declaration_type(declaration_specifiers):
    type_spec = None
    specs = []
    decl_specs = []
    for spec in declaration_specifiers:
        spec_type = spec["type"]
        if spec_type is CTypeQualifier:
            specs.append(spec["name"])
        elif spec_type is CDeclSpec:
            decl_specs.append(spec["name"])
        else:
            if type_spec is None:
                type_spec = spec
            else:
                if type_spec["name"] in spec_and_name:
                    # E.g. unsigned int, signed long long
                    specs.append(type_spec["name"])
                    type_spec = spec
                else:
                    # E.g. `int int` or `int short`
                    raise ValueError(
                        "multiple type names: %s, %s" % (type_spec, spec)
                    )
    if type_spec is None:
        raise ValueError("no type (name) specified")

    specs.append(type_spec["name"])

    spec_type_name = " ".join(specs)

    if decl_specs:
        raise NotImplementedError

    try:
        return Type[spec_type_name]
    except TypeNotRegistered:
        if type_spec["base"]:
            return Type(
                name = spec_type_name,
                base = True,
                incomplete = type_spec["name"] == "void",
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
