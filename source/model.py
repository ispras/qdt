__all__ = [
    "TypeNotRegistered"
  , "Type"
      , "Structure"
      , "Function"
      , "Pointer"
      , "Macro"
      , "MacroUsage"
      , "Enumeration"
      , "EnumerationElement"
      , "OpaqueCode"
        , "TypeAlias"
        , "TopComment"
  , "Initializer"
  , "Variable"
  , "TypeReferencesVisitor"
  , "NodeVisitor"
]

from itertools import (
    count,
)
from common import (
    ee,
    ObjectVisitor,
    SkipVisiting
)
from six import (
    add_metaclass,
    string_types,
    text_type,
    binary_type
)
from collections import (
    OrderedDict
)
from .code_gen_helpers import (
    gen_array_declaration,
)
from .type_container import (
    TypeContainer,
)


# List of coding style specific code generation settings.

# Pointers are automatically re-directed to declarations of types if available.
POINTER_TO_DECLARATION = ee("QDT_POINTER_TO_DECLARATION", "True")


# Source code models


class CPP(object):
    "This class used as definer for CPPMacro"
    references = set()


class registry(type):
    """ Provides dict-like access to a class with a `lookup` `classmethod`.
It's to be used as a `__metaclass__`.

Ex.: MyClassWithInstanceRegistry["instance id"]

References:
* https://stackoverflow.com/a/12447078/7623015
    """

    def __getitem__(self, path):
        # `self` is a `type` instance here
        return self.lookup(path)


# Type models


def iter_deref(type_):
    "Iterates wrapping nameless pointer types including backing type."
    while True:
        yield type_
        if not isinstance(type_, Pointer) or type_.is_named:
            break
        type_ = type_.type


class TypeNotRegistered(RuntimeError):
    pass


def pointer_name(name):
    asterisks = 0
    while True:
        name = name.rstrip()
        if name[-1] == '*':
            asterisks += 1
            name = name[:-1]
        else:
            break

    return name, asterisks


@add_metaclass(registry)
class Type(TypeContainer):
    reg = {}

    @staticmethod
    def lookup(name):
        name, asterisks = pointer_name(name)

        if name not in Type.reg:
            raise TypeNotRegistered("Type with name %s is not registered"
                % name
            )

        t = Type.reg[name]
        while asterisks:
            t = Pointer(t)
            asterisks -= 1

        return t

    @staticmethod
    def exists(name):
        try:
            Type[name]
            return True
        except TypeNotRegistered:
            return False

    def __init__(self,
        name = None,
        incomplete = True,
        base = False,
        **kw
    ):
        super(Type, self).__init__(**kw)

        self.is_named = name is not None

        self.incomplete = incomplete
        self.definer = None
        self.base = base

        if self.is_named:
            self.name = name
            self.c_name = name.split('.', 1)[0]

            t = Type.reg.setdefault(name, self)
            if t is not self:
                raise RuntimeError("Type %s is already registered (%s)" % (
                    name, t.definer
                ))

    def gen_var(self, name,
        pointer = False,
        initializer = None,
        static = False,
        const = False,
        array_size = None,
        used = False
    ):
        if self.incomplete:
            if not pointer:
                raise ValueError("Cannot create non-pointer variable %s"
                    " of incomplete type %s." % (name, self)
                )

        _type = Pointer(self) if pointer else self

        return Variable(name, _type,
            initializer = initializer,
            static = static,
            const = const,
            array_size = array_size,
            used = used
        )

    def __call__(self, *args, **kw):
        return self.gen_var(*args, **kw)

    def get_definers(self):
        if self.definer is None:
            return []
        else:
            return [self.definer]

    def gen_usage_string(self, initializer):
        # Usage string for an initializer is code of the initializer. It is
        # legacy behavior.
        return initializer.code

    def __eq__(self, other):
        # This code assumes that one type cannot be represented by several
        # objects.
        return self is other

    def __hash__(self):
        if self.is_named:
            return hash(self.name)
        else:
            return hash(id(self))

    def __str__(self):
        if self.is_named:
            return self.name
        else:
            raise RuntimeError("Stringifying generic nameless type")

    def __lt__(self, other):
        if not isinstance(other, (Type, Variable)):
            return NotImplemented
        return self.name < other.name

    @property
    def asterisks(self):
        "String of * required to full dereference of this as a pointer."
        return "*" * (len(list(iter_deref(self))) - 1)

    @property
    def full_deref(self):
        for t in iter_deref(self):
            pass # We only need last `t` value.
        # Note that at least one loop iteration always takes place.
        return t

    @property
    def declaration_string(self):
        return self.full_deref.c_name + "@b" + self.asterisks

    def __c__(self, writer):
        if self.is_named:
            writer.write(self.c_name)
        else:
            raise NotImplementedError


class Structure(Type):

    def __init__(self,
        name = None,
        *fields,
        **kw
    ):
        super(Structure, self).__init__(
            name = name,
            incomplete = False,
            **kw
        )

        # A `struct`ure may have a forward declaration: a `typedef` construct
        # without fields.
        #
        # typedef struct AStructure AStructure;
        #
        # If it does, the "full" declaration must not have `typedef` keyword.
        # Else, because of Qemu coding style (not C syntax), the full
        # declaration must have the keyword. Mostly because, `struct` keyword
        # is not required for variable type specification in that case.

        # Only one of those attributes may be non-`None`. If `_definition` is
        # not `None`, then `self` is forward declaration. Else, it's  "full"
        # definition (with a declaration or without).
        self.declaration = None
        self._definition = None

        self._fields = OrderedDict()
        self.append_fields(fields)

    @property
    def definition(self):
        # Note, be careful defining __bool__ or __len__.
        return self._definition or self

    def gen_forward_declaration(self):
        if not self.is_named:
            raise RuntimeError(
                "nameless structure cannot have a forward declaration"
            )

        decl = Structure(self.name + ".declaration")
        self.declaration = decl
        decl._definition = self
        return decl

    def get_field(self, name):
        return self._fields[name]

    def __getattr__(self, name):
        "Tries to find undefined attributes among fields."
        try:
            return self.get_field(name)
        except KeyError:
            pass
        raise AttributeError(name)

    def get_definers(self):
        if self.is_named:
            if self.definer is None:
                raise RuntimeError("Getting definers for structure %s that is"
                    " not added to a source" % self
                )
            definers = [self.definer]
        else:
            definers = []

        for f in self.fields.values():
            definers.extend(f.get_definers())

        return definers

    def append_field(self, variable):
        v_name = variable.name
        if v_name in self.fields:
            raise RuntimeError("A field with name %s already exists in"
                " the structure %s" % (v_name, self)
            )

        if isinstance(variable, Type):
            if variable.definer is not None:
                raise RuntimeError(
                    "Type '%s' is already defined in '%s'" % (
                        variable, variable.definer.path
                    )
                )
            variable.definer = self

        self.fields[v_name] = variable

    def append_fields(self, fields):
        for v in fields:
            self.append_field(v)

    def append_field_t(self, _type, name, pointer = False):
        self.append_field(_type(name, pointer = pointer))

    def append_field_t_s(self, type_name, name, pointer = False):
        self.append_field_t(Type[type_name], name, pointer)

    def gen_usage_string(self, init):
        if init is None:
            return "{ 0 };" # zero structure initializer by default

        code = init.code
        if not isinstance(code, dict):
            # Support for legacy initializers
            return code

        # Use entries of given dict to initialize fields. Field name is used
        # as entry key.

        fields_code = []
        for name in self.fields.keys():
            try:
                val_str = init[name]
            except KeyError: # no initializer for this field
                continue
            fields_code.append("    .%s@b=@s%s" % (name, val_str))

        return "{\n" + ",\n".join(fields_code) + "\n}";

    @property
    def fields(self):
        definition = self._definition
        if definition is None:
            return self._fields
        else:
            print("Getting fields from declaration of %s" % definition)
            return definition.fields

    @property
    def _fields_tr(self):
        "Fields for type references analysis."
        if self._definition is None:
            # It's a definition. A forward declaration cannot have fields.
            # Hence, all fields are in _and only in_ `self._fields`.
            # And the `property`s logic is not required for this case.
            return self._fields
        else:
            return []

    __type_references__ = ["_fields_tr"]

    def __str__(self):
        if self.is_named:
            return super(Structure, self).__str__()
        else:
            return "nameless structure"


class Enumeration(Type):

    def __init__(self, elems_list,
        enum_name = None,
        typedef_name = None,
        **kw
    ):
        super(Enumeration, self).__init__(
            name = typedef_name or enum_name,
            incomplete = False,
            **kw
        )

        self.enum_name = enum_name
        self.typedef_name = typedef_name
        self.typedef = typedef_name is not None

        if self.is_named and not self.typedef:
            # overwrite `c_name` to generate a correct variable type name
            self.c_name = "enum@b" + self.c_name

        self.elems = OrderedDict()
        t = [ Type["int"] ]
        for elem in elems_list:
            # Either ("name", value) tuple or just a "name" `str`ing.
            if isinstance(elem, str):
                key = elem
                init = None
            else:
                key, val = elem
                init = Initializer(str(val), t)

            self.elems[key] = EnumerationElement(self, key, init)

    def get_field(self, name):
        return self.elems[name]

    def __getattr__(self, name):
        "Tries to find undefined attributes among elements."
        try:
            return self.get_field(name)
        except KeyError:
            pass
        raise AttributeError(name)

    def get_definers(self):
        if self.definer is None:
            raise RuntimeError("Getting definers for enumeration %s that is"
                " not added to a source", self
            )

        definers = [self.definer]

        for f in self.elems.values():
            definers.extend(f.get_definers())

        return definers

    def __str__(self):
        if self.is_named:
            return super(Enumeration, self).__str__()
        else:
            return "anonymous enumeration"

    __type_references__ = ["elems"]


class EnumerationElement(Type):

    def __init__(self, enum_parent, name, initializer,
        **kw
    ):
        super(EnumerationElement, self).__init__(
            name = name,
            **kw
        )

        self.enum_parent = enum_parent
        self.initializer = initializer

    def get_definers(self):
        if self.definer is None:
            raise RuntimeError("Getting definers for enumeration element %s"
                " that is not added to a source", self
            )

        definers = [self.definer]

        if self.initializer is not None:
            for t in self.initializer.used_types:
                definers.extend(t.get_definers())

        return definers

    def __int__(self):
        "Predicts `int`eger equivalent of the `enum`eration element."
        # XXX: currently works for simple auto enumerated `enum`s.
        return list(self.enum_parent.elems.values()).index(self)

    def __or__(self, arg):
        from .function import (
            OpOr
        )
        return OpOr(self, arg)

    __type_references__ = ["initializer"]


class FunctionBodyString(TypeContainer):

    def __init__(self,
        body = None,
        used_types = None,
        used_globals = None,
        **kw
    ):
        super(FunctionBodyString, self).__init__(**kw)

        self.body = body
        self.used_types = set() if used_types is None else set(used_types)
        self.used_globals = [] if used_globals is None else list(used_globals)

        for i in self.used_globals:
            i.used = True

    def __str__(self):
        return self.body

    __type_references__ = ["used_types"]
    __node__ = ["used_globals"]


class Function(Type):

    def __init__(self,
        name = None,
        body = None,
        ret_type = None,
        args = None,
        static = False,
        inline = False,
        used_types = None,
        used_globals = None,
        **kw
    ):
        # args is list of Variables

        super(Function, self).__init__(
            name = name,
            # function cannot be a 'type' of variable. Only function
            # pointer type is permitted.
            incomplete = True,
            **kw
        )

        # XXX: eliminate all usages of empty c_name
        if not self.is_named:
            self.c_name = ""

        self.static = static
        self.inline = inline
        self.ret_type = Type["void"] if ret_type is None else ret_type
        self.args = args
        self.declaration = None

        # Under Py2 body can be `unicode`.
        if isinstance(body, (str, text_type)):
            self.body = FunctionBodyString(
                body = body,
                used_types = used_types,
                used_globals = used_globals
            )
        else:
            self.body = body
            if (used_types or used_globals) is not None:
                raise ValueError("Specifing of used types or globals for non-"
                    "string body is redundant."
                )

    def __getitem__(self, name_or_index):
        "Shortcut for arguments"
        if isinstance(name_or_index, str):
            for a in self.args:
                if a.name == name_or_index:
                    return a
        else:
            return self.args[name_or_index]

    def use_as_prototype(self, name,
        body = None,
        static = None,
        inline = False,
        used_types = [],
        used_globals = None
    ):
        new_f = Function(
            name = name,
            body = body,
            ret_type = self.ret_type,
            args = self.args,
            static = self.static if static is None else static,
            inline = inline,
            used_types = used_types,
            used_globals = used_globals
        )
        return new_f

    def gen_definition(self,
        body = None,
        used_types = None,
        used_globals = None
    ):
        new_f = Function(
            name = self.name + ".definition",
            body = body,
            ret_type = self.ret_type,
            args = self.args,
            static = self.static,
            inline = self.inline,
            used_types = used_types,
            used_globals = used_globals
        )
        new_f.declaration = self
        return new_f

    def gen_var(self, name, initializer = None, static = False):
        return Variable(name, Pointer(self),
            initializer = initializer,
            static = static
        )

    def __str__(self):
        if self.is_named:
            return super(Function, self).__str__()
        else:
            return "nameless function"

    __type_references__ = ["ret_type", "args", "body"]


class Pointer(Type):

    def __init__(self, _type,
        name = None,
        const = False,
        **kw
    ):
        """
        const: a constant pointer
        """
        if const:
            raise NotImplementedError(
                "A constant pointer is not fully implemented"
            )

        super(Pointer, self).__init__(
            name = name,
            incomplete = False,
            **kw
        )

        # define c_name for nameless pointers
        if not self.is_named:
            self.c_name = _type.c_name + '*'

        if POINTER_TO_DECLARATION and isinstance(_type, (Structure, Function)):
            _type = _type.declaration or _type

        self.type = _type
        self.const = const

    def __eq__(self, other):
        if not isinstance(other, Pointer):
            return False

        if self.is_named:
            if other.is_named:
                return super(Pointer, self).__eq__(other)
            return False

        if other.is_named:
            return False

        return (self.type == other.type) and (self.const == other.const)

    def get_definers(self):
        if self.is_named:
            return super(Pointer, self).get_definers()
        else:
            return self.type.get_definers()

    def __hash__(self):
        if self.is_named:
            return hash(self.name)
        else:
            return hash(hash(self.full_deref) + hash(self.asterisks))

    def __str__(self):
        if self.is_named:
            return super(Pointer, self).__str__()
        else:
            return "pointer to %s" % self.type

    def __c__(self, writer):
        if self.is_named:
            super(Pointer, self).__c__(writer)
        else:
            writer.write(self.declaration_string)

    __type_references__ = ["type"]


HDB_MACRO_NAME = "name"
HDB_MACRO_TEXT = "text"
HDB_MACRO_ARGS = "args"


class Macro(Type):

    # args is list of strings
    def __init__(self, name,
        args = None,
        text = None,
        **kw
    ):
        super(Macro, self).__init__(
            name = name,
            incomplete = False,
            **kw
        )

        self.args = args
        self.text = text

    def gen_usage_string(self, init = None):
        if self.args is None:
            return self.c_name
        else:
            arg_val = "(@a" + ",@s".join(init[a] for a in self.args) + "@c)"

        return "%s%s" % (self.c_name, arg_val)

    def gen_var(self, name,
        pointer = False,
        initializer = None,
        static = False,
        array_size = None,
        used = False,
        macro_initializer = None
    ):
        return MacroUsage(self, initializer = macro_initializer)(name,
            pointer = pointer,
            initializer = initializer,
            static = static,
            array_size = array_size,
            used = used
        )

    def gen_type(self, initializer = None, name = None, counter = count(0)):
        "A helper that automatically generates a name for `MacroUsage`."
        if name is None:
            name = self.name + ".auto" + str(next(counter))
        return MacroUsage(self, initializer = initializer, name = name)

    def gen_dict(self):
        res = {HDB_MACRO_NAME : self.name}
        if self.text is not None:
            res[HDB_MACRO_TEXT] = self.text
        if self.args is not None:
            res[HDB_MACRO_ARGS] = self.args

        return res

    @staticmethod
    def new_from_dict(_dict):
        return Macro(
            name = _dict[HDB_MACRO_NAME],
            args = _dict[HDB_MACRO_ARGS] if HDB_MACRO_ARGS in _dict else None,
            text = _dict[HDB_MACRO_TEXT] if HDB_MACRO_TEXT in _dict else None
        )


class MacroUsage(Type):
    "Something defined using a macro expansion."

    def __init__(self, macro,
        initializer = None,
        name = None,
        **kw
    ):
        if not isinstance(macro, Macro):
            raise ValueError("Attempt to create %s from "
                " %s which is not macro." % (type(self).__name__, macro)
            )

        super(MacroUsage, self).__init__(
            name = name,
            incomplete = False,
            **kw
        )

        # define c_name for nameless macrousages
        if not self.is_named:
            self.c_name = macro.gen_usage_string(initializer)

        self.macro = macro
        self.initializer = initializer

    def get_definers(self):
        if self.is_named:
            return super(MacroUsage, self).get_definers()
        else:
            return self.macro.get_definers()

    def __str__(self):
        if self.is_named:
            return super(MacroUsage, self).__str__()
        else:
            return "usage of macro %s" % self.macro

    __type_references__ = ["macro", "initializer"]


class CPPMacro(Macro):
    """ A kind of macro defined by the C preprocessor.
    For example __FILE__, __LINE__, __func__ and etc.
    """

    def __init__(self, *args, **kw):
        super(CPPMacro, self).__init__(*args, **kw)
        self.definer = CPP


class OpaqueCode(Type):
    """ MONKEY STYLE WARNING: AVOID USING THIS IF POSSIBLE !!!

Use this to insert top level code entities which are not supported by the
model yet. Better implement required functionality and submit patches!
    """

    def __init__(self, code,
        name = None,
        used_types = None,
        used_variables = None,
        weight = None,
        **kw
    ):
        """
:param code: the code (implementing `__str__`) to be inserted in file as is.
:param used_types: iterable of types to be placed above.
:param used_vars: iterable of global variables to be placed above.
    Both can be used to satisfy def-use syntax order requirements.
:param weight: overwrites default weight of `SourceChunk`.
    Use it to adjust position in file.
        """
        if name is None:
            # User does not worry about name. But the model require each
            # generated type to have a name.
            # Note, we can just use `id(self)` but a counter makes name more
            # reproducible across launches.
            name = "opaque.#%u" % next(type(self)._name_num)

        super(OpaqueCode, self).__init__(
            name = name,
            incomplete = False,
            **kw
        )

        self.code = code

        # Items are just passed to code generator to get referenced chunks.
        self.used = set() if used_types is None else set(used_types)
        if used_variables is not None:
            self.used.update(used_variables)

            for i in used_variables:
                i.used = True

        self.weight = weight

    _name_num = count()

    __type_references__ = ["used"]


class TypeAlias(OpaqueCode):

    def __init__(self, _type, name,
        **kw
    ):
        super(TypeAlias, self).__init__(
            "typedef@b" + _type.declaration_string + name + ";\n",
            name = name,
            used_types = [_type],
            **kw
        )


class TopComment(OpaqueCode):
    "Use this to insert top level and structure field comments."

    def __init__(self, text,
        used_types = None,
        used_variables = None,
        weight = None,
        **kw
    ):
        super(TopComment, self).__init__(
            "/*@s" + text.replace(" ", "@s") + "@s*/\n",
            used_types = used_types,
            used_variables = used_variables,
            weight = weight,
            **kw
        )


# Data models


class TypeReferencesVisitor(ObjectVisitor):

    __field_name__ = "__type_attributes__"


class NodeVisitor(ObjectVisitor):

    def __init__(self, root):
        super(NodeVisitor, self).__init__(root,
            field_name = "__node__"
        )


class TypesCollector(TypeReferencesVisitor):

    def __init__(self, code):
        super(TypesCollector, self).__init__(code)
        self.used_types = set()

    def on_visit(self):
        cur = self.cur
        if isinstance(cur, Type):
            self.used_types.add(cur)
            raise SkipVisiting()


class GlobalsCollector(NodeVisitor):

    def __init__(self, code):
        super(GlobalsCollector, self).__init__(code)
        self.used_globals = set()

    def on_visit(self):
        cur = self.cur
        if (    isinstance(cur, Variable)
            and (cur.declarer is not None or cur.definer is not None)
        ):
            self.used_globals.add(cur)


class ForwardDeclarator(TypeReferencesVisitor):
    """ This visitor detects a cyclic type dependency and replaces the
    structure declaration with a forward declaration of the structure
    """

    def on_visit(self):
        t = self.cur
        if isinstance(t, Structure) and t in self.previous:
            if t.declaration is not None:
                decl = t.declaration
            else:
                decl = t.gen_forward_declaration()
                if t.definer is not None:
                    t.definer.add_type(decl)

            self.replace(decl)


class Initializer(TypeContainer):

    # code is string for variables and dictionary for macros
    def __init__(self, code,
        used_types = [],
        used_variables = [],
        **kw
    ):
        super(Initializer, self).__init__(**kw)

        self.code = code
        self.used_types = set(used_types)
        self.used_variables = used_variables
        if isinstance(code, dict):
            # automatically get types used in the code
            self.used_types.update(TypesCollector(code).visit().used_types)

    def __getitem__(self, key):
        val = self.code[key]

        # adjust initializer value
        if isinstance(val, (string_types, text_type, binary_type)):
            val_str = val
        elif isinstance(val, Type):
            val_str = val.c_name
        else:
            raise TypeError("Unsupported initializer entry type '%s'"
                % type(val).__name__
            )

        return val_str

    # Note, if `code` is a `str`ing, the type analysis just ignore it.
    __type_references__ = ["used_types", "used_variables", "code"]


class Variable(TypeContainer):

    def __init__(self, name, _type,
        initializer = None,
        static = False,
        const = False,
        array_size = None,
        used = False,
        **kw
    ):
        super(Variable, self).__init__(**kw)

        self.name = name
        if isinstance(_type, str):
            _type = Type[_type]
        self.type = _type
        self.initializer = initializer
        self.static = static
        self.const = const
        self.array_size = array_size
        self.used = used
        # a header
        self.declarer = None
        # a module
        self.definer = None

    @property
    def asterisks(self):
        return self.type.asterisks

    @property
    def full_deref(self):
        return self.type.full_deref

    @property
    def declaration_string(self):
        return "{static}{const}{type}{var}{array_decl}".format(
            static = "static@b" if self.static else "",
            const = "const@b" if self.const else "",
            type = self.type.declaration_string,
            var = self.name,
            array_decl = gen_array_declaration(self.array_size)
        )

    def gen_callback(self, *args, **kw):
        "Generate a function suitable for that function pointer"
        return self.type.type.use_as_prototype(*args, **kw)

    def get_definers(self):
        return self.type.get_definers()

    def __c__(self, writer):
        writer.write(self.name)

    def __str__(self):
        return self.name

    def __lt__(self, other):
        if not isinstance(other, (Type, Variable)):
            return NotImplemented
        return self.name < other.name

    __type_references__ = ["type", "initializer"]
