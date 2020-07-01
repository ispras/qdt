__all__ = [
    "TypeNotRegistered"
  , "Type"
      # must not be used externally
      # "TypeReference"
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

from copy import (
    copy
)
from itertools import (
    count,
)
from common import (
    ee,
    path2tuple,
    ObjectVisitor,
    BreakVisiting
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
from .chunks import (
    HeaderInclusion,
    MacroDefinition,
    MacroTypeChunk,
    PointerTypeDeclaration,
    FunctionPointerTypeDeclaration,
    FunctionPointerDeclaration,
    VariableDeclaration,
    VariableDefinition,
    StructureForwardDeclaration,
    StructureOpeningBracket,
    StructureClosingBracket,
    StructureTypedefDeclarationBegin,
    StructureTypedefDeclarationEnd,
    StructureDeclarationBegin,
    StructureDeclarationEnd,
    StructureVariableDeclarationBegin,
    StructureVariableDeclarationEnd,
    EnumerationDeclarationBegin,
    EnumerationDeclarationEnd,
    EnumerationElementDeclaration,
    FunctionDeclaration,
    FunctionDefinition,
    OpaqueChunk,
)


# List of coding style specific code generation settings.

# Pointers are automatically re-directed to declarations of types if available.
POINTER_TO_DECLARATION = ee("QDT_POINTER_TO_DECLARATION", "True")

# Add a new line after the opening curly bracket in the structure without
# fields
ADD_NL_IN_EMPTY_STRUCTURE = ee("QDT_ADD_NL_IN_EMPTY_STRUCTURE", "False")


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


@add_metaclass(registry)
class Type(object):
    reg = {}

    @staticmethod
    def lookup(name):
        if name not in Type.reg:
            raise TypeNotRegistered("Type with name %s is not registered"
                % name
            )
        return Type.reg[name]

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
        base = False
    ):
        self.is_named = name is not None

        self.incomplete = incomplete
        self.definer = None
        self.base = base

        if self.is_named:
            self.name = name
            self.c_name = name.split('.', 1)[0]

            if name in Type.reg:
                raise RuntimeError("Type %s is already registered" % name)

            Type.reg[name] = self

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

    def gen_chunks(self, generator):
        raise ValueError("Attempt to generate source chunks for stub"
            " type %s" % self
        )

    def gen_defining_chunk_list(self, generator, **kw):
        if self.base:
            return []
        else:
            return self.gen_chunks(generator, **kw)

    def gen_usage_string(self, initializer):
        # Usage string for an initializer is code of the initializer. It is
        # legacy behavior.
        return initializer.code

    def __eq__(self, other):
        if isinstance(other, TypeReference):
            return other.type == self
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


class TypeReference(Type):

    def __init__(self, _type):
        if isinstance(_type, TypeReference):
            raise ValueError("Attempt to create type reference to"
                " another type reference %s." % _type
            )

        # Do not pass name to Type.__init__ to prevent TypeReference addition
        # to the registry.
        super(TypeReference, self).__init__(
            incomplete = _type.incomplete,
            base = _type.base
        )

        self.name = _type.name
        self.c_name = _type.c_name
        self.type = _type
        self.definer_references = None

    def get_definers(self):
        return self.type.get_definers()

    def gen_chunks(self, generator):
        if self.definer_references is None:
            raise RuntimeError("Attempt to generate chunks for reference to"
                " type %s without the type reference adjusting"
                " pass." % self
            )

        definer = self.type.definer

        refs = []
        for r in self.definer_references:
            chunks = generator.provide_chunks(r)

            if not chunks:
                continue

            # not only `HeaderInclusion` can satisfies reference
            if isinstance(chunks[0], HeaderInclusion):
                chunks[0].add_reason(r, kind = "satisfies %s by" % definer)

            refs.extend(chunks)

        if definer is CPP:
            return refs
        else:
            inc = HeaderInclusion(definer)
            inc.add_references(refs)
            inc.add_reason(self.type)
            return [inc]

    def gen_var(self, *args, **kw):
        raise ValueError("Attempt to generate variable of type %s"
            " using a reference" % self.type
        )

    def gen_usage_string(self, initializer):
        # redirect to referenced type
        return self.type.gen_usage_string(initializer)

    __type_references__ = ["definer_references"]

    def __eq__(self, other):
        return self.type == other

    def __hash__(self):
        return hash(self.type)

    def __c__(self, writer):
        self.type.__c__(writer)

    def __str__(self):
        return str(self.type)


class Structure(Type):

    def __init__(self, name = None, *fields):
        super(Structure, self).__init__(name = name, incomplete = False)

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

        ForwardDeclarator(variable).visit()

    def append_fields(self, fields):
        for v in fields:
            self.append_field(v)

    def append_field_t(self, _type, name, pointer = False):
        self.append_field(_type(name, pointer = pointer))

    def append_field_t_s(self, type_name, name, pointer = False):
        self.append_field_t(Type[type_name], name, pointer)

    def gen_fields_chunks(self, generator, struct_begin, struct_end,
        indent = ""
    ):
        fields_indent = "    "
        need_nl = ADD_NL_IN_EMPTY_STRUCTURE or bool(self.fields)

        """
        References map of structure definition chunks:

              ____--------> [self references of struct_begin ]
             /    ___-----> [ united references of all fields ]
            |    /     _--> [ references of struct_end ] == empty
            |    |    /
            |    |   |
           struct_begin
                ^
                |
          opening bracket
                ^
                |
             field_0
                ^
                |
             field_1
                ^
                |
               ...
                ^
                |
             field_N
                ^
                |
          closing bracket
                ^
                |
            struct_end

        """

        field_indent = indent + fields_indent
        field_refs = []

        br = StructureOpeningBracket(self, need_nl)
        br.add_reference(struct_begin)
        top_chunk = br

        for f in self.fields.values():
            field_chunks = generator.provide_chunks(f, indent = field_indent)
            # believe that we got a list of chunks in the format
            # [end, ..., begin] or [single_chunk] and the last (begin) chunk
            # accumulates all outer references of the chunk subtree

            field_decl = field_chunks[-1]
            field_refs.extend(list(field_decl.references))
            field_decl.clean_references()
            field_decl.add_reference(top_chunk)
            top_chunk = field_chunks[0]

        struct_begin.add_references(field_refs)

        br = StructureClosingBracket(self, indent if need_nl else "")
        br.add_reference(top_chunk)
        struct_end.add_reference(br)

    def gen_chunks(self, generator, indent = ""):
        if not self.is_named:
            raise AssertionError("chunks for a nameless structure are "
                "generated by the variable having that structure immediately "
                "in its declaration"
            )

        if self._definition is not None:
            return [StructureForwardDeclaration(self, indent)]

        if self.declaration is None:
            struct_begin = StructureTypedefDeclarationBegin(self, indent)
            struct_end = StructureTypedefDeclarationEnd(self)
        else:
            struct_begin = StructureDeclarationBegin(self, indent)
            struct_end = StructureDeclarationEnd(self)

        self.gen_fields_chunks(generator, struct_begin, struct_end, indent)

        return [struct_end, struct_begin]

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
        if self._definition is None:
            return self._fields
        else:
            print("Warning: getting fields from structure declaration")
            return self._definition.fields

    @property
    def __type_references__(self):
        if self._definition is None:
            # It's a definition. A forward declaration cannot have fields.
            # Hence, all fields are in _and only in_ `self._fields`.
            # And the `property`s logic is not required for this case.
            return ["_fields"]
        else:
            return []

    def __c__(self, writer):
        writer.write(self.c_name)

    def __str__(self):
        if self.is_named:
            return super(Structure, self).__str__()
        else:
            return "nameless structure"


class Enumeration(Type):

    def __init__(self, elems_list, enum_name = None, typedef_name = None):
        super(Enumeration, self).__init__(
            name = typedef_name or enum_name,
            incomplete = False
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
            if isinstance(elem, str):
                key, val = elem, ""
            else:
                key, val = elem

            self.elems[key] = EnumerationElement(self, key,
                Initializer(str(val), t)
            )

    def get_field(self, name):
        return self.elems[name]

    def __getattr__(self, name):
        "Tries to find undefined attributes among elements."
        try:
            return self.get_field(name)
        except KeyError:
            pass
        raise AttributeError(name)

    def gen_chunks(self, generator):
        fields_indent = "    "
        indent = ""

        enum_begin = EnumerationDeclarationBegin(self, indent)
        enum_end = EnumerationDeclarationEnd(self, indent)

        field_indent = indent + fields_indent
        field_refs = []
        top_chunk = enum_begin

        last_num = len(self.elems) - 1
        for i, f in enumerate(self.elems.values()):
            field_declaration = EnumerationElementDeclaration(f,
                indent = field_indent,
                separ = "" if i == last_num else ","
            )
            field_declaration.add_reference(top_chunk)

            if f.initializer is not None:
                for t in f.initializer.used_types:
                    field_refs.extend(list(generator.provide_chunks(t)))

            top_chunk = field_declaration

        enum_begin.add_references(field_refs)
        enum_end.add_reference(top_chunk)

        return [enum_end, enum_begin]

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

    def __init__(self, enum_parent, name, initializer):
        super(EnumerationElement, self).__init__(name = name)

        self.enum_parent = enum_parent
        self.initializer = initializer

    def gen_chunks(self, generator, **kw):
        return list(generator.provide_chunks(self.enum_parent, **kw))

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

    def __c__(self, writer):
        writer.write(self.c_name)

    __type_references__ = ["initializer"]


class FunctionBodyString(object):

    def __init__(self, body = None, used_types = None, used_globals = None):
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
        used_globals = None
    ):
        # args is list of Variables

        super(Function, self).__init__(
            name = name,
            # function cannot be a 'type' of variable. Only function
            # pointer type is permitted.
            incomplete = True
        )

        # XXX: eliminate all usages of empty c_name
        if not self.is_named:
            self.c_name = ""

        self.static = static
        self.inline = inline
        self.ret_type = Type["void"] if ret_type is None else ret_type
        self.args = args
        self.declaration = None

        if isinstance(body, str):
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

    def gen_declaration_chunks(self, generator):
        indent = ""
        ch = FunctionDeclaration(self, indent)

        refs = gen_function_decl_ref_chunks(self, generator)

        ch.add_references(refs)

        return [ch]

    gen_chunks = gen_declaration_chunks

    def gen_definition_chunks(self, generator):
        indent = ""
        ch = FunctionDefinition(self, indent)

        refs = (gen_function_decl_ref_chunks(self, generator) +
            gen_function_def_ref_chunks(self, generator)
        )

        ch.add_references(refs)
        return [ch]

    def use_as_prototype(self, name,
        body = None,
        static = None,
        inline = False,
        used_types = []
    ):
        new_f = Function(
            name = name,
            body = body,
            ret_type = self.ret_type,
            args = self.args,
            static = self.static if static is None else static,
            inline = inline,
            used_types = used_types
        )
        CopyFixerVisitor(new_f).visit()
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
        CopyFixerVisitor(new_f).visit()
        new_f.declaration = self
        return new_f

    def gen_var(self, name, initializer = None, static = False):
        return Variable(name, Pointer(self),
            initializer = initializer,
            static = static
        )

    def __c__(self, writer):
        writer.write(self.c_name)

    def __str__(self):
        if self.is_named:
            return super(Function, self).__str__()
        else:
            return "nameless function"

    __type_references__ = ["ret_type", "args", "body"]


class Pointer(Type):

    def __init__(self, _type, name = None, const = False):
        """
        const: a constant pointer
        """
        if const:
            raise NotImplementedError(
                "A constant pointer is not fully implemented"
            )

        super(Pointer, self).__init__(name = name, incomplete = False)

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

    def gen_chunks(self, generator):
        type = self.type

        # `Function` related helpers below can't get a `TypeReference`.
        # `func` variable is added to solve it.
        if isinstance(type, TypeReference):
            func = type.type
            is_function = isinstance(func, Function)
        elif isinstance(type, Function):
            func = type
            is_function = True
        else:
            is_function = False

        # strip function definition chunk, its references is only needed
        if is_function:
            refs = gen_function_decl_ref_chunks(func, generator)
        else:
            refs = generator.provide_chunks(type)

        if not self.is_named:
            return refs

        name = self.c_name

        if is_function:
            ch = FunctionPointerTypeDeclaration(func, name)
        else:
            ch = PointerTypeDeclaration(type, name)

        """ 'typedef' does not require referenced types to be visible.
Hence, it is not correct to add references to the PointerTypeDeclaration
chunk. The references is to be added to `users` of the 'typedef'.
        """
        ch.add_references(refs)

        return [ch]

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

    __type_references__ = ["type"]


HDB_MACRO_NAME = "name"
HDB_MACRO_TEXT = "text"
HDB_MACRO_ARGS = "args"


class Macro(Type):

    # args is list of strings
    def __init__(self, name, args = None, text = None):
        super(Macro, self).__init__(name = name, incomplete = False)

        self.args = args
        self.text = text

    def gen_chunks(self, generator):
        return [ MacroDefinition(self) ]

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

    def __c__(self, writer):
        writer.write(self.c_name)


class MacroUsage(Type):
    "Something defined using a macro expansion."

    def __init__(self, macro, initializer = None, name = None):
        if not isinstance(macro, Macro):
            raise ValueError("Attempt to create %s from "
                " %s which is not macro." % (type(self).__name__, macro)
            )

        super(MacroUsage, self).__init__(name = name, incomplete = False)

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

    def gen_chunks(self, generator, indent = ""):
        macro = self.macro
        initializer = self.initializer

        refs = list(generator.provide_chunks(macro))

        if initializer is not None:
            for v in initializer.used_variables:
                refs.extend(generator.provide_chunks(v))

            for t in initializer.used_types:
                refs.extend(generator.provide_chunks(t))

        if self.is_named:
            ch = MacroTypeChunk(self, indent)
            ch.add_references(refs)
            return [ch]
        else:
            return refs

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

    def gen_chunks(self, _):
        # CPPMacro does't require referenced types
        # because it's defined by C preprocessor.
        return []


class OpaqueCode(Type):
    """ MONKEY STYLE WARNING: AVOID USING THIS IF POSSIBLE !!!

Use this to insert top level code entities which are not supported by the
model yet. Better implement required functionality and submit patches!
    """

    def __init__(self, code,
        name = None,
        used_types = None,
        used_variables = None,
        weight = None
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

        super(OpaqueCode, self).__init__(name = name, incomplete = False)

        self.code = code

        # Items are just passed to code generator to get referenced chunks.
        self.used = set() if used_types is None else set(used_types)
        if used_variables is not None:
            self.used.update(used_variables)

            for i in used_variables:
                i.used = True

        self.weight = weight

    _name_num = count()

    def gen_chunks(self, generator, indent = ""):
        ch = OpaqueChunk(self, indent)

        for item in self.used:
            ch.add_references(generator.provide_chunks(item))

        return [ch]

    __type_references__ = ["used"]


class TypeAlias(OpaqueCode):

    def __init__(self, _type, name):
        super(TypeAlias, self).__init__(
            "typedef@b" + _type.declaration_string + name + ";\n",
            name = name,
            used_types = [_type]
        )


class TopComment(OpaqueCode):
    "Use this to insert top level and structure field comments."

    def __init__(self, text,
        used_types = None,
        used_variables = None,
        weight = None
    ):
        super(TopComment, self).__init__(
            "/*@s" + text.replace(" ", "@s") + "@s*/\n",
            used_types = used_types,
            used_variables = used_variables,
            weight = weight
        )


# Data models


class TypeReferencesVisitor(ObjectVisitor):

    def __init__(self, root):
        super(TypeReferencesVisitor, self).__init__(root,
            field_name = "__type_references__"
        )


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
            raise BreakVisiting()


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

    def __init__(self, variable):
        super(ForwardDeclarator, self).__init__(variable)

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


class Initializer(object):

    # code is string for variables and dictionary for macros
    def __init__(self, code, used_types = [], used_variables = []):
        self.code = code
        self.used_types = set(used_types)
        self.used_variables = used_variables
        if isinstance(code, dict):
            self.__type_references__ = self.__type_references__ + ["code"]

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

    __type_references__ = ["used_types", "used_variables"]


class Variable(object):

    def __init__(self, name, _type,
        initializer = None,
        static = False,
        const = False,
        array_size = None,
        used = False
    ):
        self.name = name
        self.type = _type if isinstance(_type, Type) else Type[_type]
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

    def gen_declaration_chunks(self, generator,
        indent = "",
        extern = False
    ):
        type_ = self.type
        if (    isinstance(type_, Structure)
            and not type_.is_named
        ):
            var_begin = StructureVariableDeclarationBegin(self, indent)
            var_end = StructureVariableDeclarationEnd(self)
            type_.gen_fields_chunks(generator, var_begin, var_end, indent)
            return [var_end, var_begin]
        elif (    isinstance(type_, Pointer)
              and not type_.is_named
              and isinstance(type_.type, Function)
        ):
            ch = FunctionPointerDeclaration(self, indent, extern)
            refs = gen_function_decl_ref_chunks(type_.type, generator)
        else:
            ch = VariableDeclaration(self, indent, extern)
            refs = generator.provide_chunks(type_)
        ch.add_references(refs)

        return [ch]

    def get_definition_chunks(self, generator,
        indent = "",
        append_nl = True,
        separ = ";"
    ):
        ch = VariableDefinition(self, indent, append_nl, separ)

        refs = list(generator.provide_chunks(self.type))

        if self.initializer is not None:
            for v in self.initializer.used_variables:
                refs.extend(generator.provide_chunks(v))

            for t in self.initializer.used_types:
                refs.extend(generator.provide_chunks(t))

        ch.add_references(refs)
        return [ch]

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

# Type inspecting


    """
    CopyVisitor is now used for true copying function body arguments
    in order to prevent wrong TypeReferences among them
    because before function prototype and body had the same args
    references (in terms of python references)
    """


class CopyFixerVisitor(TypeReferencesVisitor):

    def on_visit(self):
        t = self.cur

        if (not isinstance(t, Type)
            or (isinstance(t, (Pointer, MacroUsage)) and not t.is_named)
        ):
            new_t = copy(t)

            self.replace(new_t, skip_trunk = False)
        else:
            raise BreakVisiting()


def gen_function_decl_ref_chunks(function, generator):
    references = list(generator.provide_chunks(function.ret_type))

    if function.args is not None:
        for a in function.args:
            references.extend(generator.provide_chunks(a.type))

    return references


def gen_function_def_ref_chunks(f, generator):
    references = []

    for t in TypesCollector(f.body).visit().used_types:
        references.extend(generator.provide_chunks(t))

    for t in GlobalsCollector(f.body).visit().used_globals:
        references.extend(generator.provide_chunks(t))

    return references
