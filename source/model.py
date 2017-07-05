from os import \
    listdir

from os.path import \
    basename, \
    splitext, \
    split, \
    join, \
    isdir

from copy import \
    copy

import sys

# PLY`s C preprocessor is used for several QEMU code analysis
ply = join(split(split(__file__)[0])[0], "ply")
if ply not in sys.path:
    sys.path.insert(0, ply)

from ply.lex import lex
from ply.cpp import *

from common import \
    OrderedSet, \
    ObjectVisitor, \
    BreakVisiting

from itertools import \
    count

from six import \
    string_types, text_type, binary_type

# Used for sys.stdout recovery
sys_stdout_recovery = sys.stdout

# Source code models

class Source(object):
    def __init__(self, path):
        self.path = path
        self.types = {}
        self.inclusions = {}
        self.global_variables = {}
        self.usages = []
        self.references = set()

    def add_reference(self, ref):
        if not isinstance(ref, Type):
            raise Exception('Trying to add source reference '
                            'which is not a Type object')
        if isinstance(ref, TypeReference):
            raise Exception("""Source reference may not be TypeReference.
 Only original types are allowed."""
            )
        self.references.add(ref)

        return self

    def add_references(self, refs):
        for ref in refs:
            self.add_reference(ref)

        return self

    def add_usage(self, usage):
        TypeFixerVisitor(self, usage).visit()

        self.usages.append(usage)

        return self

    def add_global_variable(self, var):
        if var.name in self.global_variables:
            raise Exception("Variable with name %s is already in file %s"
                % (var.name, self.name))

        TypeFixerVisitor(self, var).visit()

        # Auto add definers for type
        for s in var.type.get_definers():
            if s == self:
                continue
            if not type(s) == Header:
                raise Exception("Attempt to define variable %s whose type \
is defined in non-header file %s" % (var.name, s.path))
            self.add_inclusion(s)
        # Auto add definers for types used by variable initializer
        if type(self) is Source:
            if var.initializer is not None:
                for t in var.initializer.used_types:
                    for s in t.get_definers():
                        if s == self:
                            continue
                        if not type(s) == Header:
                            raise Exception("Attempt to define variable {var} \
whose initializer code uses type {t} defined in non-header file {file}".format(
    var = var.name,
    t = t.name,
    file = s.path
)
                            )
                        self.add_inclusion(s)

        self.global_variables[var.name] = var

        return self

    def add_inclusion(self, header):
        if not type(header) == Header:
            raise Exception("Inclusion of non-header file {} is forbidden"
                .format(header.path))

        if not header.path in self.inclusions:
            self.inclusions[header.path] = header

            for t in header.types.values():
                try:
                    if type(t) == TypeReference:
                        self._add_type_recursive(TypeReference(t.type))
                    else:
                        self._add_type_recursive(TypeReference(t))
                except AddTypeRefToDefinerException:
                    # inclusion cycles will cause this exceptions
                    pass

            if self in header.includers:
                raise Exception("Header %s is in %s includers but does not \
includes it" % (self.path, header.path))

            header.includers.append(self)

        return self

    def _add_type_recursive(self, type_ref):
        if type_ref.name in self.types:
            t = self.types[type_ref.name]
            if type(t) == TypeReference:
                # To check incomplete type case
                if not t.type.definer == type_ref.type.definer:
                    raise Exception("""Conflict reference to type {} \
found in source {}. The type is defined both in {} and {}.\
""".format(t.name, self.path, type_ref.type.definer.path, t.type.definer.path))
            # To make more conflicts checking
            return False

        self.types[type_ref.name] = type_ref
        return True

    def add_types(self, types):
        for t in types:
            self.add_type(t)

        return self

    def add_type(self, _type):
        if type(_type) == TypeReference:
            raise Exception("""A type reference ({}) cannot be 
added to a source ({}) externally""".format(_type.name, self.path))

        TypeFixerVisitor(self, _type).visit()

        _type.definer = self
        self.types[_type.name] = _type

        # Auto include type definers
        for s in _type.get_definers():
            if s == self:
                continue
            if not type(s) == Header:
                raise Exception("Attempt to define structure {} that has \
a field of a type defined in another non-header file {}.".format(
    _type.name, s.path))
            self.add_inclusion(s)

        return self

    def gen_chunks(self, inherit_references = False):
        """ In some use cases header should not satisfy references of its
inclusions by itself. Instead, it must inherit them. A source file must
satisfy the references in such case. Set inherit_references to True for
switching to that mode.
        """

        if inherit_references:
            assert(isinstance(self, Header))

        chunks = []
        ref_list = []

        if isinstance(self, Header):
            for user in self.includers:
                for ref in user.references:
                    if ref.definer not in user.inclusions:
                        ref_list.append(TypeReference(ref))


        # fix up types for headers with references
        # list of types must be copied because it is changed during each
        # loop iteration. values() returns generator in Python 3.x, which
        # must be explicitly enrolled to a list. Though is it redundant
        # copy operation in Python 2.x.
        l = list(self.types.values()) + ref_list

        while True:
            for t in l:
                if not isinstance(t, TypeReference):
                    continue

                if t.definer_references is not None:
                    # References are already specified
                    continue

                if inherit_references:
                    t.definer_references = set()
                    for ref in t.type.definer.references:
                        for self_ref in self.references:
                            if self_ref is ref:
                                break
                        else:
                            self.references.add(ref)
                else:
                    t.definer_references = set(t.type.definer.references)

            replaced = False
            for t in l:
                if not isinstance(t, TypeReference):
                    continue
    
                tfv = TypeFixerVisitor(self, t)
                tfv.visit()

                if tfv.replaced:
                    replaced = True

            if not replaced:
                break
            # Preserve current types list. See the comment above.
            l = list(self.types.values()) + ref_list

        for t in self.types.values():
            if isinstance(t, TypeReference):
                for inc in self.inclusions.values():
                    if t.name in inc.types:
                        break
                else:
                    raise RuntimeError("Any type reference in a file must "
"be provided by at least one inclusion (%s: %s)" % (self.path, t.name)
                    )
                continue

            if t.definer is not self:
                raise RuntimeError("Type %s is defined in %s but presented in"
" %s not by a reference." % (t.name, t.definer.path, self.path)
                )

            if type(t) is Function:
                if type(self) is Header and (not t.static or not t.inline):
                    chunks.extend(t.gen_declaration_chunks())
                else:
                    chunks.extend(t.gen_definition_chunks())
            else:
                chunks.extend(t.gen_chunks())

        if type(self) == Header:
            for gv in self.global_variables.values():
                chunks.extend(gv.gen_declaration_chunks(extern = True))
            for r in ref_list:
                chunks.extend(r.gen_chunks())

        elif type(self) == Source:
            for gv in self.global_variables.values():
                chunks.extend(gv.get_definition_chunks())

        for u in self.usages:
            chunks.extend(u.gen_chunks())

        return chunks

    def generate(self, inherit_references = False):
        Header.propagate_references()

        source_basename = basename(self.path)
        name = splitext(source_basename)[0]

        file = SourceFile(name, type(self) == Header)

        file.add_chunks(self.gen_chunks(inherit_references))

        return file

class AddTypeRefToDefinerException (Exception):
    pass

class ParsePrintFilter:
    def __init__(self, out):
        self.out = out
        self.written = False

    def write(self, str):
        if str.startswith("Info:"):
            self.out.write(str + "\n")
            self.written = True

    def flush(self):
        if self.written:
            self.out.flush()
            self.written = False

class Header(Source):
    reg = {}

    @staticmethod
    def _on_include(includer, inclusion, is_global):
        if not inclusion in Header.reg:
            print("Parsing " + inclusion + " as inclusion")
            h = Header(path = inclusion, is_global = is_global)
            h.parsed = True
        else:
            h = Header.lookup(inclusion)

        Header.lookup(includer).add_inclusion(h)

    @staticmethod
    def _on_define(definer, macro):
        # macro is ply.cpp.Macro

        if "__FILE__" == macro.name:
            return

        h = Header.lookup(definer)

        try:
            m = Type.lookup(macro.name)
            if not m.definer.path == definer:
                print("Info: multiple definitions of macro %s in %s and %s"\
                     % (macro.name, m.definer.path, definer)
                )
        except:
            m = Macro(
                name = macro.name,
                text = macro.value[0].value,
                args = (
                    None if macro.arglist is None else list(macro.arglist)
                )
            )
            h.add_type(m)

    @staticmethod
    def _build_inclusions_recursive(start_dir, prefix):
        full_name = join(start_dir, prefix)
        if (isdir(full_name)):
            for entry in listdir(full_name):
                yield Header._build_inclusions_recursive(
                    start_dir,
                    join(prefix, entry)
                )
        else:
            (name, ext) = splitext(prefix)
            if ext == ".h":
                if not prefix in Header.reg:
                    h = Header(path = prefix, is_global = False)
                    h.parsed = False
                else:
                    h = Header.lookup(prefix)

                if not h.parsed:
                    h.parsed = True
                    print("Info: parsing " + prefix)

                    p = Preprocessor(lex())
                    p.add_path(start_dir)

                    # Default include search folders should be specified to
                    # locate and parse standard headers.
                    # TODO: parse `cpp -v` output to get actual list of default
                    # include folders. It should be cross-platform
                    p.add_path("/usr/include")

                    p.on_include = Header._on_include
                    p.on_define.append(Header._on_define)

                    header_input = open(full_name, "r").read()
                    p.parse(input = header_input, source = prefix)

                    yields_per_current_header = 0

                    tokens_before_yield = 0
                    while p.token():
                        if not tokens_before_yield:

                            yields_per_current_header += 1

                            yield True
                            tokens_before_yield = 1000 # an adjusted value
                        else:
                            tokens_before_yield -= 1

                    Header.yields_per_header.append(yields_per_current_header)

        raise StopIteration()

    @staticmethod
    def co_build_inclusions(dname):
        Header.yields_per_header = []

        if not isinstance(sys.stdout, ParsePrintFilter):
            sys.stdout = ParsePrintFilter(sys.stdout)

        for h in Header.reg.values():
            h.parsed = False

        for entry in listdir(dname):
            yield Header._build_inclusions_recursive(dname, entry)

        for h in Header.reg.values():
            del h.parsed

        sys.stdout = sys_stdout_recovery

        yields_total = sum(Header.yields_per_header)

        print("""Header inclusions build statistic:
    Yields total: %d
    Max yields per header: %d
    Min yields per header: %d
    Average yields per headed: %f
""" % (
    yields_total,
    max(Header.yields_per_header),
    min(Header.yields_per_header),
    yields_total / float(len(Header.yields_per_header))
)
        )

        del Header.yields_per_header

        raise StopIteration()


    @staticmethod
    def build_inclusions(dname):
        gen = Header.co_build_inclusions(dname)

        try:
            while True:
                next(gen)
        except StopIteration:
            pass

    @staticmethod
    def lookup(path):
        if not path in Header.reg:
            raise Exception("Header with path %s is not registered"
                % path)
        return Header.reg[path] 

    def __init__(self, path, is_global=False):
        super(Header, self).__init__(path)
        self.is_global = is_global
        self.includers = []

        if path in Header.reg:
            raise Exception("Header %s is already registered" % path)

        Header.reg[path] = self

    def _add_type_recursive(self, type_ref):
        if type_ref.type.definer == self:
            raise AddTypeRefToDefinerException("Adding type %s reference to \
file %s defining the type" % (type_ref.type.name, self.path))

        # Preventing infinite recursion by header inclusion loop
        if super(Header, self)._add_type_recursive(type_ref):
            # Type was added. Hence, It is new type for the header
            for s in self.includers:
                try:
                    s._add_type_recursive(TypeReference(type_ref.type))
                except AddTypeRefToDefinerException:
                    # inclusion cycles will cause this exception
                    pass

    def add_type(self, _type):
        super(Header, self).add_type(_type)

        # Auto add type references to self includers
        for s in self.includers:
            s._add_type_recursive(TypeReference(_type))

        return self

    def __hash__(self):
        # key contains of 'g' or 'h' and header path
        # 'g' and 'h' are used to distinguish global and local
        # headers with same 
        return hash("{}{}".format(
                "g" if self.is_global else "l",
                self.path))

    @staticmethod
    def _propagate_reference(h, ref):
        h.add_reference(ref)

        for u in h.includers:
            if type(u) == Source:
                continue
            if ref in u.references:
                continue
            """ u is definer of ref or u has type reference to ref (i.e.
transitively includes definer of ref)"""
            if ref.name in u.types:
                continue
            Header._propagate_reference(u, ref)

    @staticmethod
    def propagate_references():
        for h in Header.reg.values():
            if not isinstance(h, Header):
                continue

            for ref in h.references:
                for u in h.includers:
                    if type(u) == Source:
                        continue
                    if ref in u.references:
                        continue
                    if ref.name in u.types:
                        continue
                    Header._propagate_reference(u, ref)

# Type models

class TypeNotRegistered(Exception):
    pass

class Type(object):
    reg = {}

    @staticmethod
    def lookup(name):
        if not name in Type.reg:
            raise TypeNotRegistered("Type with name %s is not registered"
                % name)
        return Type.reg[name]

    @staticmethod
    def exists(name):
        try:
            Type.lookup(name)
            return True
        except TypeNotRegistered:
            return False

    def __init__(self, name, incomplete=True, base=False):
        self.name = name
        self.incomplete = incomplete
        self.definer = None
        self.base = base

        if name in Type.reg:
            raise Exception("Type %s is already registered" % name)

        Type.reg[name] = self

    def gen_var(self, name, pointer = False, initializer = None,
                static = False, array_size = None):
        if self.incomplete:
            if not pointer:
                raise Exception("Cannon create non-pointer variable {} \
of incomplete type {}.".format(name, self.name))

        if pointer:
            pt = Pointer(self)
            return Variable(name = name, _type = pt,
                initializer = initializer, static = static,
                array_size = array_size)
        else:
            return Variable(name = name, _type = self,
                initializer = initializer, static = static,
                array_size = array_size)

    def get_definers(self):
        if self.definer is None:
            return []
        else:
            return [self.definer]

    def gen_chunks(self):
        raise Exception("Attempt to generate source chunks for type {}"
            .format(self.name))

    def gen_defining_chunk_list(self):
        if self.base:
            return []
        else:
            return self.gen_chunks()

    def gen_usage_string(self, initializer):
        # Usage string for an initializer is code of the initializer. It is
        # legacy behaviour.
        return initializer.code

    def __eq__(self, other):
        if isinstance(other, TypeReference):
            return other.type == self
        # This code assumes that one type cannot be represented by several
        # objects.
        return self is other

    def __hash__(self):
        return hash(self.name)

class TypeReference(Type):
    def __init__(self, _type):
        if type(_type) == TypeReference:
            raise Exception("Cannot create type reference to type \
reference {}.".format(_type.name))

        #super(TypeReference, self).__init__(_type.name, _type.incomplete)
        self.name = _type.name
        self.incomplete = _type.incomplete
        self.base = _type.base
        self.type = _type

        self.definer_references = None

    def get_definers(self):
        return self.type.get_definers()

    def gen_chunks(self):
        if self.definer_references is None:
            raise Exception("""Attempt to generate chunks for %s type reference\
 without the type reference adjusting pass""" % self.name
            )

        inc = HeaderInclusion(self.type.definer)

        refs = []
        for r in self.definer_references:
            refs.extend(r.gen_defining_chunk_list())

        inc.add_references(refs)
        return [inc] + refs

    gen_defining_chunk_list = gen_chunks

    def gen_var(self, name, pointer = False, initializer = None,
            static = False):
        raise Exception("""Attempt to generate variable of type %s by
 reference""" % self.type.name)

    def gen_usage_string(self, initializer):
        # redirect to referenced type
        return self.type.gen_usage_string(initializer)

    __type_references__ = ["definer_references"]

    def __eq__(self, other):
        return self.type == other

    def __hash__(self):
        return hash(self.type)

class Structure(Type):
    def __init__(self, name, fields = None):
        super(Structure, self).__init__(name, incomplete=False)
        self.fields = []
        if fields is not None:
            for v in fields:
                self.append_field(v)

    def get_definers(self):
        if self.definer is None:
            raise Exception("Getting definers for structure {} that \
is not added to a source", self.name)

        definers = [self.definer]

        for f in self.fields:
            definers.extend(f.type.get_definers())

        return definers


    def append_field(self, variable):
        for f in self.fields:
            if f.name == variable.name:
                raise Exception("""Field with name {} already exists
 in structure {}""".format(f.name, self.name))

        self.fields.append(variable)

    def append_field_t(self, _type, name, pointer = False):
        self.append_field(_type.gen_var(name, pointer))

    def append_field_t_s(self, type_name, name, pointer = False):
        self.append_field_t(Type.lookup(type_name), name, pointer)

    def gen_chunks(self):
        return StructureDeclaration.gen_chunks(self)

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
        for f in self.fields:
            try:
                val_str = init[f.name]
            except KeyError: # no initializer for this field
                continue
            fields_code.append("    .%s = %s" % (f.name, val_str))

        return "{\n" + ",\n".join(fields_code) + "\n}";

    __type_references__ = ["fields"]

class Function(Type):
    def __init__(self,
            name,
            body = None,
            ret_type = None,
            args = None,
            static = False, 
            inline = False,
            used_types = [],
            used_globals = []):
        # args is list of Variables
        super(Function, self).__init__(name,
            # function cannot be a 'type' of variable. Only function
            # pointer type is permitted.
            incomplete=True)
        self.static = static
        self.inline = inline
        self.body = body
        self.ret_type = Type.lookup("void") if ret_type is None else ret_type
        self.args = args
        self.used_types = set(used_types)
        self.used_globals = used_globals

    def gen_declaration_chunks(self):
        return FunctionDeclaration.gen_chunks(self)

    def gen_definition_chunks(self):
        return FunctionDefinition.gen_chunks(self)

    def gen_chunks(self):
        return FunctionDeclaration.gen_chunks(self)

    def use_as_prototype(self,
        name,
        body = None,
        static = False,
        inline = False,
        used_types = []):

        return Function(name, body, self.ret_type, self.args, static, inline,
            used_types)

    def gen_body(self):
        new_f = Function(
            self.name + '.body',
            self.body,
            self.ret_type,
            list(self.args),
            self.static,
            self.inline,
            [self],
            list(self.used_globals)
        )
        CopyFixerVisitor(new_f).visit()
        return new_f

    def gen_var(self, name, initializer = None, static = False):
        return Variable(name = name, _type = self, 
                initializer = initializer, static = static)

    __type_references__ = ["ret_type", "args", "used_types", "used_globals"]

class Pointer(Type):
    def __init__(self, _type, name=None, const = False):
        """
        const: pointer to constant (not a constant pointer).
        """
        self.is_named = name is not None
        if not self.is_named:
            name = _type.name + '*'
            if const:
                name = "const " + name

        # do not add nameless pointers to type registry
        if self.is_named:
            super(Pointer, self).__init__(name,
                incomplete = False,
                base = False)
        else:
            self.name = name
            self.incomplete = False
            self.base = False

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

    def gen_chunks(self):
        # strip function definition chunk, its references is only needed
        if isinstance(self.type, Function):
            refs = gen_function_decl_ref_chunks(self.type)
        else:
            refs = self.type.gen_defining_chunk_list()

        if self.is_named:
            ch = PointerTypeDeclaration(self.type, self.name)

            """ 'typedef' does not require refererenced types to be visible.
Hence, it is not correct to add references to the PointerTypeDeclaration
chunk. The references is to be added to 'users' of the 'typedef'.
        """
            ch.add_references(refs)

            return [ch] + refs
        else:
            return refs

    def __hash__(self):
        stars = "*"
        t = self.type
        while isinstance(t, Pointer) and not t.is_named:
            t = t.type
            stars += "*"
        return hash(hash(t) + hash(stars))

    __type_references__ = ["type"]

class Macro(Type):
    # args is list of strings
    def __init__(self, name, args = None, text=None):
        super(Macro, self).__init__(name, incomplete = False)

        self.args = args
        self.text = text

    def gen_chunks(self):
        return [ MacroDefinition(self) ]

    def gen_usage_string(self, init = None):
        if self.args is None:
            return self.name
        else:
            arg_val = "(" + ", ".join(init[a] for a in self.args) + ")"

        return "%s%s" % (self.name, arg_val)

    def gen_var(self, pointer = False, inititalizer = None, static = False):
        return super(Macro, self).gen_var(
                name = "fake variable of macro %s" % self.name
            )

    def gen_dict(self):
        res = {"name" : self.name}
        if self.text is not None:
            res["text"] = self.text
        if self.args is not None:
            res["args"] = self.args

        return res

    @staticmethod
    def new_from_dict(_dict):
        return Macro(
            name = _dict["name"],
            args = None if not "args" in _dict else _dict["args"],
            text = None if not "text" in _dict else _dict["text"]
            )

# Data models

class InitCodeVisitor(ObjectVisitor):
    def __init__(self, code):
        super(InitCodeVisitor, self).__init__(code,
            field_name = "__type_references__"
        )
        self.used_types = set()

    def on_visit(self):
        cur = self.cur
        if isinstance(cur, Type):
            self.used_types.add(cur)
            raise BreakVisiting()

class Initializer():
    #code is string for variables and dictionary for macros
    def __init__(self, code, used_types = [], used_variables = []):
        self.code = code
        self.used_types = set(used_types)
        self.used_variables = used_variables
        if isinstance(code, dict):
            self.__type_references__ = self.__type_references__ + ["code"]

            # automatically get types used in the code
            icv = InitCodeVisitor(code)
            icv.visit()
            self.used_types.update(icv.used_types)

    def __getitem__(self, key):
        val = self.code[key]

        # adjust initializer value
        if isinstance(val, (string_types, text_type, binary_type)):
            val_str = val
        elif isinstance(val, Type):
            val_str = val.name
        else:
            raise TypeError("Unsupported initializer entry type '%s'"
                % type(val).__name__
            )

        return val_str

    __type_references__ = ["used_types", "used_variables"]

class Variable():
    def __init__(self, name, _type, initializer = None, static = False,
                 array_size = None):
        self.name = name
        self.type = _type
        self.initializer = initializer
        self.static = static
        self.array_size = array_size

    def gen_declaration_chunks(self, indent="", extern = False):
        if isinstance(self.type, Pointer) and not self.type.is_named:
            return PointerVariableDeclaration.gen_chunks(self, indent, extern)
        else:
            return VariableDeclaration.gen_chunks(self, indent, extern)

    def get_definition_chunks(self, indent=""):
        return VariableDefinition.gen_chunks(self, indent)

    def gen_usage(self, initializer = None):
        return Usage(self, initializer)

    __type_references__ = ["type", "initializer"]

# Type inspecting

class TypeFixerVisitor(ObjectVisitor):
    def __init__(self, source, type_object, *args, **kw):
        kw["field_name"] = "__type_references__"
        ObjectVisitor.__init__(self, type_object, *args, **kw)

        self.source = source
        self.replaced = False

    def replace(self, new_value):
        self.replaced = True
        ObjectVisitor.replace(self, new_value)

    def on_visit(self):
        if isinstance(self.cur, Type):
            t = self.cur
            if isinstance(t, TypeReference):
                try:
                    self_tr = self.source.types[t.name]
                except KeyError:
                    # The source does not have such type reference
                    self.source.add_inclusion(t.type.definer)
                    self_tr = self.source.types[t.name]

                if self_tr is not t:
                    self.replace(self_tr)

                raise BreakVisiting()

            if t.base:
                raise BreakVisiting()

            """ Skip pointer types without name. Nameless pointer does not have
            definer and should not be replaced with type reference """
            if isinstance(t, Pointer) and not t.is_named:
                return

            # Do not add definerless types to the Source automatically
            if t.definer is None:
                return

            if t.definer is self.source:
                return

            try:
                tr = self.source.types[t.name]
            except KeyError:
                self.source.add_inclusion(t.definer)
                # Now a reference to type t must be in types of the source
                tr = self.source.types[t.name]

            self.replace(tr)

    """
    CopyVisitor is now used for true copying function body arguments
    in order to prevent wrong TypeReferences among them
    because before function prototype and body had the same args
    references (in terms of python references)
    """

class CopyFixerVisitor(ObjectVisitor):
    def __init__(self, type_object, *args, **kw):
        kw["field_name"] = "__type_references__"
        ObjectVisitor.__init__(self, type_object, *args, **kw)

    def on_visit(self):
        t = self.cur
        if isinstance(t, Variable) or \
            isinstance(t, Usage) or \
            isinstance(t, Initializer) or \
            (isinstance(t, Pointer) and not t.is_named):
            new_t = copy(t)
            if isinstance(t, Initializer):
                new_t.used_variables = list(t.used_variables)
                new_t.used_types = set(t.used_types)
            try:
                self.replace(new_t)
            except BreakVisiting:
                pass

        else:
            raise BreakVisiting

# Function and instruction models

class Usage():
    def __init__(self, var, initializer = None):
        self.variable = var
        self.initalizer = initializer

    def gen_chunks(self):
        ret = VariableUsage.gen_chunks(self.variable, self.initalizer)
        # do not add semicolon after macro usage
        if not (type(self.variable.type) == Macro \
            or isinstance(self.variable.type, TypeReference) and \
                isinstance(self.variable.type.type, Macro) \
        ):
            term_chunk = SourceChunk(
                name = "Variable %s usage terminator" % self.variable.name,
                code = ";\n",
                references = ret)
            ret.append(term_chunk)

        return ret 

    __type_references__ = ["variable", "initalizer"]

class Operand():
    def __init__(self, name, data_references=[]):
        self.name = name
        self.data_references = data_references

class VariableOperand(Operand):
    def __init__(self, var):
        super(VariableOperand, self).__init__(
            "reference to variable {}".format(var.name), [var])

class Operator():
    def __init__(self, fmt, operands):
        self.format = fmt
        self.operands = operands

class BinaryOperator(Operator):
    def __init__(self, name, operands):
        fmt = "{{}} {} {{}}".format(name);
        super(BinaryOperator, self).__init__(fmt, operands)

class AssignmentOperator(BinaryOperator):
    def __init__(self, operands):
        super(AssignmentOperator, self).__init__("=", operands)


class CodeNode():
    def __init__(self, name, code, used_types=None, node_references=None):
        self.name = name
        self.code = code
        self.node_users = []
        self.node_references = []
        self.used_types = set()

# Source code instances

class SourceChunk(object):
    def __init__(self, name, code, references = None):
        # visited is used during deep first sort
        self.name = name
        self.code = code
        self.visited = 0
        self.users = set()
        self.references = set()
        self.source = None
        if references is not None:
            for chunk in references:
                self.add_reference(chunk)

    def add_reference(self, chunk):
        self.references.add(chunk)
        chunk.users.add(self)

    def add_references(self, refs):
        for r in refs:
            self.add_reference(r)

    def del_reference(self, chunk):
        self.references.remove(chunk)
        chunk.users.remove(self)

    def clean_references(self):
        for r in list(self.references):
            self.del_reference(r)

    def check_cols_fix_up(self, max_cols = 80, indent='    '):
        lines = self.code.split('\n')
        code = ''
        auto_new_line = ' \\\n{}'.format(indent)
        last_line = len(lines) - 1

        for idx, line in enumerate(lines):
            if idx == last_line and len(line) == 0:
                break;

            if len(line) > max_cols:
                line_no_indent_len = len(line) - len(line.lstrip(' '))
                line_indent = line[:line_no_indent_len]

                words = line.lstrip(' ').split(' ')

                ll = 0
                for word in words:
                    if ll > 0:
                        # The variable r reserves characters for auto new
                        # line ' \\' that can be added after current word 
                        if word == words[-1]:
                            r = 0
                        else:
                            r = 2
                        if 1 + r + len(word) + ll > max_cols:
                            code += auto_new_line + line_indent + word
                            ll = len(indent) + len(line_indent) + len(word)
                        else:
                            code += ' ' + word
                            ll += 1 + len(word)
                    else:
                        code += line_indent + word
                        ll += len(line_indent) + len(word)
                code += '\n'
            else:
                code += line + '\n'

        self.code = code

class HeaderInclusion(SourceChunk):
    def __init__(self, header):
        super(HeaderInclusion, self).__init__(
            name = "Header {} inclusion".format(header.path),
            references=[],
            code = """\
#include {}{}{}
""".format(
        ( "<" if header.is_global else "\"" ),
        header.path,
        ( ">" if header.is_global else "\"" ),
    )
            )
        self.header = header

    def get_origin(self):
        return self.header

class MacroDefinition(SourceChunk):
    def __init__(self, macro, indent = ""):
        if macro.args is None:
            args_txt = ""
        else:
            args_txt = "("
            for a in macro.args[:-1]:
                args_txt += a + ", "
            args_txt += macro.args[-1] + ")"

        super(MacroDefinition, self).__init__(
            name = "Definition of macro %s" % macro.name,
            code = "%s#define %s%s%s" % (
                indent,
                macro.name,
                args_txt,
                "" if macro.text is None else " %s" % macro.text)
            )

        self.macro = macro

    def get_origin(self):
        return self.macro

class PointerTypeDeclaration(SourceChunk):
    def __init__(self, _type, def_name):
        self.type = _type
        self.def_name = def_name
        name = 'Definition of pointer to type' + self.type.name

        if type(self.type) == Function:
            code = 'typedef ' + gen_function_declaration_string('', self.type, def_name)
            code += ';\n'
        else:
            code = 'typedef ' + self.type.name + ' ' + def_name

        super(PointerTypeDeclaration, self).__init__(name, code)

    def get_origin(self):
        return self.type

class PointerVariableDeclaration(SourceChunk):
    @staticmethod
    def gen_chunks(var, indent="", extern=False):
        ch = PointerVariableDeclaration(var, indent, extern)

        if isinstance(var.type.type, Function):
            refs = gen_function_decl_ref_chunks(var.type.type)
        else:
            refs = var.type.type.gen_defining_chunk_list()
        ch.add_references(refs)

        return [ch] + refs

    def __init__(self, var, indent="", extern = False):
        self.var = var
        t = var.type.type
        if type(t) == Function:
            code = """\
{indent}{extern}{decl_str};
""".format(
                indent = indent,
                extern = "extern " if extern else "",
                decl_str = gen_function_declaration_string('', t, var.name,
                                                           var.array_size)
                )
        else:
            code = """\
{indent}{extern}{type_name} *{var_name};
""".format(
                indent = indent,
                type_name = t.name,
                var_name = var.name,
                extern = "extern " if extern else ""
            )
        super(PointerVariableDeclaration, self).__init__(
            name = "Declaration of pointer {} to type {}".format(
                var.name,
                t.name
            ),
            code = code
        )

    def get_origin(self):
        return self.var


class VariableDeclaration(SourceChunk):
    @staticmethod
    def gen_chunks(var, indent = "", extern = False):
        t = var.type if not isinstance(var.type, TypeReference)\
            else var.type.type

        if type(t) == Macro:
            u = VariableUsage.gen_chunks(var, indent = indent)
            ch = u[0]
            refs = u[1:]
        else:
            ch = VariableDeclaration(var, indent, extern)
            refs = var.type.gen_defining_chunk_list()

        ch.add_references(refs)

        return [ch] + refs

    def __init__(self, var, indent="", extern = False):
        super(VariableDeclaration, self).__init__(
            name = "Variable {} of type {} declaration".format(
                var.name,
                var.type.name
                ),
            code = """\
{indent}{extern}{type_name} {var_name}{array_decl};
""".format(
        indent = indent,
        type_name = var.type.name,
        var_name = var.name,
        array_decl =  gen_array_declaration(var.array_size),
        extern = "extern " if extern else ""
    )
            )
        self.variable = var

    def get_origin(self):
        return self.variable

class VariableDefinition(SourceChunk):
    @staticmethod
    def gen_chunks(var, indent="", append_nl = True):
        ch = VariableDefinition(var, indent, append_nl)

        refs = var.type.gen_defining_chunk_list()
        if var.initializer is not None:
            for v in var.initializer.used_variables:
                # Note that 0-th chunk is variable and rest are its dependencies
                refs.append(v.get_definition_chunks()[0])

            for t in var.initializer.used_types:
                refs.extend(t.gen_defining_chunk_list())

        ch.add_references(refs)
        return [ch] + refs

    def __init__(self, var, indent="", append_nl = True):
        init_code = ''
        if var.initializer is not None:
            raw_code = var.type.gen_usage_string(var.initializer)
            # add indent to initializer code
            init_code_lines = raw_code.split('\n')
            init_code = " = " + init_code_lines[0]
            for line in init_code_lines[1:]:
                init_code += "\n" + indent + line

        self.variable = var

        super(VariableDefinition, self).__init__(
            name = "Variable %s of type %s definition" %
                (var.name, var.type.name),
            code = """\
{indent}{static}{type_name} {var_name}{array_decl}{init};{nl}
""".format(
        indent = indent,
        static = "static " if var.static else "",
        type_name = var.type.name,
        var_name = var.name,
        array_decl = gen_array_declaration(var.array_size),
        init = init_code,
        nl = "\n" if append_nl else ""
    )
            )

    def get_origin(self):
        return self.variable

class VariableUsage(SourceChunk):
    @staticmethod
    def gen_chunks(var, initializer = None, indent = ""):
        ch = VariableUsage(var, initializer, indent)

        refs = var.type.gen_defining_chunk_list()

        if initializer is not None:
            for v in initializer.used_variables:
                """ Note that 0-th chunk is variable and rest are its
                dependencies """
                refs.append(v.get_definition_chunks()[0])

            for t in initializer.used_types:
                refs.extend(t.gen_defining_chunk_list())

        ch.add_references(refs)
        return [ch] + refs

    def __init__(self, var, initializer = None, indent = ""):
        super(VariableUsage, self).__init__(
            name = "Usage of variable of type %s" % var.type.name,
            code = indent + var.type.gen_usage_string(initializer)
        )

        self.variable = var
        self.indent = indent
        self.initializer = initializer


    def get_origin(self):
        return self.variable

class StructureDeclarationBegin(SourceChunk):
    @staticmethod
    def gen_chunks(struct, indent = ""):
        ch = StructureDeclarationBegin(struct, indent)
        return [ch]

    def __init__(self, struct, indent):
        self.structure = struct
        super(StructureDeclarationBegin, self).__init__(
            name="Beginning of structure {} declaration".format(struct.name),
            code="""\
{indent}typedef struct _{struct_name} {{
""".format(
                indent=indent,
                struct_name=struct.name
            )
        )

    def get_origin(self):
        return self.structure

class StructureDeclaration(SourceChunk):
    @staticmethod
    def gen_chunks(struct,
        fields_indent = "    ",
        indent = "",
        append_nl = True
    ):
        struct_begin = StructureDeclarationBegin.gen_chunks(struct, indent)[0]

        struct_end = StructureDeclaration(struct, fields_indent, indent,
            append_nl)

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
            struct_end

        """

        field_indent = "{}{}".format(indent, fields_indent)
        field_refs = []
        field_chunks = []
        top_chunk = struct_begin

        for f in struct.fields:
            # Note that 0-th chunk is field and rest are its dependencies
            decl_chunks = f.gen_declaration_chunks(field_indent)
            field_declaration = decl_chunks[0]

            field_refs.extend(decl_chunks[1:])
            field_declaration.clean_references()
            field_declaration.add_reference(top_chunk)
            field_chunks.append(field_declaration)
            top_chunk = field_declaration

        struct_begin.add_references(field_refs)
        struct_end.add_reference(top_chunk)

        return [struct_end, struct_begin] + field_chunks

    def get_origin(self):
        return self.structure

    def __init__(self, struct, fields_indent="    ", indent="",
                 append_nl = True):
        super(StructureDeclaration, self).__init__(
            name = "Ending of structure {} declaration".format(struct.name),
            code = """\
{indent}}} {struct_name};{nl}
""".format(
    indent = indent,
    struct_name = struct.name,
    nl = "\n" if append_nl else ""
    ),
            )

        self.structure = struct

def gen_array_declaration(array_size):
    if array_size is not None:
        if array_size == 0:
            array_decl = '[]'
        elif array_size > 0:
            array_decl = '[' + str(array_size) + ']'
    else:
        array_decl = ''
    return array_decl

def gen_function_declaration_string(indent, function, pointer_name = None,
                                    array_size = None):
    if function.args is None:
        args = "void"
    else:
        args = ""
        for a in function.args:
            args += a.type.name + " " + a.name
            if not a == function.args[-1]:
                args += ", "

    if function.name.find('.body') != -1:
        decl_name = function.name[:-5]
    else:
        decl_name = function.name

    return "{indent}{static}{inline}{ret_type}{name}({args})".format(
        indent = indent,
        static = "static " if function.static else "",
        inline = "inline " if function.inline else "",
        ret_type = function.ret_type.name + " ",
        name = decl_name if pointer_name is None else ('(*' + pointer_name +
                                                       gen_array_declaration(array_size) + ')'),
        args = args
    )

def gen_function_decl_ref_chunks(function):
    references = function.ret_type.gen_defining_chunk_list() 

    if function.args is not None:
        for a in function.args:
            references.extend(a.type.gen_defining_chunk_list())

    return references

def gen_function_def_ref_chunks(f):
    references = []

    for t in f.used_types:
        references.extend(t.gen_defining_chunk_list())

    for g in f.used_globals:
        # Note that 0-th chunk is the global and rest are its dependencies
        references.append(g.get_definition_chunks()[0])

    return references

class FunctionDeclaration(SourceChunk):
    @staticmethod
    def gen_chunks(function, indent = ""):
        ch = FunctionDeclaration(function, indent)

        refs = gen_function_decl_ref_chunks(function)

        ch.add_references(refs)

        return [ch] + refs

    def __init__(self, function, indent = ""):
        super(FunctionDeclaration, self).__init__(
            name = "Declaration of function %s" % function.name,
            code = "%s;" % gen_function_declaration_string(indent, function)
            )
        self.function = function

    def get_origin(self):
        return self.function

class FunctionDefinition(SourceChunk):
    @staticmethod
    def gen_chunks(function, indent = "", append_nl = True):
        ch = FunctionDefinition(function, indent)

        refs = gen_function_decl_ref_chunks(function) + \
               gen_function_def_ref_chunks(function)

        ch.add_references(refs)
        return [ch] + refs

    def __init__(self, function, indent = "", append_nl = True):
        body = " {}" if function.body is None else "\n{\n%s}" % function.body

        if append_nl:
            body +="\n"

        super(FunctionDefinition, self).__init__(
            name = "Definition of function %s" % function.name,
            code = "{dec}{body}\n".format(
                dec = gen_function_declaration_string(indent, function),
                body = body
                )
            )
        self.function = function

    def get_origin(self):
        return self.function

def deep_first_sort(chunk, new_chunks):
    # visited: 
    # 0 - not visited
    # 1 - visited
    # 2 - added to new_chunks
    chunk.visited = 1
    for ch in chunk.references:
        if ch.visited == 2:
            continue
        if ch.visited == 1:
            raise Exception("A loop is found in source chunk references")
        deep_first_sort(ch, new_chunks)

    chunk.visited = 2
    new_chunks.append(chunk)

def source_chunk_key(ch):
    try:
        return {
            HeaderInclusion: 0,
            StructureDeclaration: 1,
            VariableDeclaration: 2,
            VariableDefinition: 3,
            FunctionDeclaration: 5,
            FunctionDefinition: 6
        }[type(ch)]
    except KeyError:
        return 4

class SourceFile:
    def __init__(self, name, is_header=False):
        self.name = name
        self.is_header = is_header
        self.chunks = []
        self.sort_needed = False

    def gen_chunks_graph(self, w):
        w.write("""\
digraph Chunks {
    rankdir=BT;
    node [shape=polygon fontname=Momospace]
    edge [style=filled]

"""
        )

        w.write("    /* Chunks */\n")

        def chunk_node_name(chunk, mapping = {}, counter = count(0)):
            try:
                name = mapping[chunk]
            except KeyError:
                name = "ch_%u" % next(counter)
                mapping[chunk] = name
            return name

        for ch in self.chunks:
            cnn = chunk_node_name(ch)
            w.write('\n    %s [label="%s"]\n' % (cnn, ch.name))
            if ch.references:
                w.write("        /* References */\n")
                for ref in ch.references:
                    w.write("        %s -> %s\n" % (cnn, chunk_node_name(ref)))

        w.write("}\n")

    def gen_chunks_gv_file(self, file_name):
        f = open(file_name, "w")
        self.gen_chunks_graph(f)
        f.close()

    def remove_dup_chunk(self, ch, ch_remove):
        for user in list(ch_remove.users):
            user.del_reference(ch_remove)
            # prevent self references
            if user is not ch:
                user.add_reference(ch)

        self.chunks.remove(ch_remove)

    def remove_chunks_with_same_origin(self, types = []):
        for t in types:
            exists = {}

            for ch in list(self.chunks):
                if not type(ch) == t:
                    continue

                origin = ch.get_origin()

                try:
                    ech = exists[origin]
                except KeyError:
                    exists[origin] = ch
                    continue

                self.remove_dup_chunk(ech, ch)

                self.sort_needed = True

    def sort_chunks(self):
        if not self.sort_needed:
            return

        new_chunks = []
        # topology sorting
        for chunk in self.chunks:
            if not chunk.visited == 2:
                deep_first_sort(chunk, new_chunks)

        for chunk in new_chunks:
            chunk.visited = 0

        self.chunks = new_chunks

    def add_chunks(self, chunks):
        for ch in chunks:
            self.add_chunk(ch)

    def add_chunk(self, chunk):
        if chunk.source is None:
            self.sort_needed = True
            self.chunks.append(chunk)

            # Also add referenced chunks into the source
            for ref in chunk.references:
                self.add_chunk(ref)
        elif not chunk.source == self:
            raise Exception("The chunk {} is already in {} ".format(
                chunk.name, chunk.source.name))

    def optimize_inclusions(self, log = lambda *args, **kw : None):
        log("-= inclusion optimization started for %s.%s =-" % (
            (self.name, "h" if self.is_header else "c")
        ))

        # use 'visited' flag to prevent dead loop in case of inclusion cycle
        for h in Header.reg.values():
            h.visited = False
            h.root = None

        # Dictionary is used for fast lookup HeaderInclusion by Header.
        # Assuming only one inclusion per header.
        included_headers = {}

        for ch in self.chunks:
            if type(ch) == HeaderInclusion:
                h = ch.header
                if h in included_headers:
                    raise RuntimeError("Duplicate inclusions must be removed "
                        " before inclusion optimization."
                    )
                included_headers[h] = ch
                # root is originally included header.
                h.root = h

        log("Originally included:\n"
            + "\n".join(h.path for h in included_headers)
        )

        stack = list(included_headers)

        while stack:
            h = stack.pop()

            for sp in h.inclusions:
                s = Header.lookup(sp)
                if s in included_headers:
                    """ If an originally included header (s) is transitively
included from another one (h.root) then inclusion of s is redundant and must
be deleted. All references to it must be redirected to inclusion of h (h.root).
                    """
                    redundant = included_headers[s]
                    substitution = included_headers[h.root]

                    """ Because the header inclusion graph is not acyclic,
a header can (transitively) include itself. Then nothing is to be substituted.
                    """
                    if redundant is substitution:
                        log("Cycle: " + s.path)
                        continue

                    if redundant.header is not s:
                        # inclusion of s was already removed as redundant
                        log("%s includes %s which already substituted by "
                            "%s" % (h.root.path, s.path, redundant.header.path)
                        )
                        continue

                    log("%s includes %s, substitute %s with %s" % (
                        h.root.path, s.path, redundant.header.path,
                        substitution.header.path
                    ))

                    self.remove_dup_chunk(substitution, redundant)

                    """ The inclusion of s was removed but s could transitively
include another header (s0) too. Then inclusion of any s0 must be removed and
all references to it must be redirected to inclusion of h. Hence, reference to
inclusion of h must be remembered. This algorithm keeps it in included_headers
replacing reference to removed inclusion of s. If s was processed before h then
there could be several references to inclusion of s in included_headers. All of
them must be replaced with reference to h. """
                    for hdr, chunk in included_headers.items():
                        if chunk is redundant:
                            included_headers[hdr] = substitution

                if s.root is None:
                    stack.append(s)
                    # Keep reference to originally included header.
                    s.root = h.root

        # Clear runtime variables
        for h in Header.reg.values():
            del h.visited
            del h.root

        log("-= inclusion optimization ended =-")

    def check_static_function_declarations(self):
        func_dec = {}
        for ch in list(self.chunks):
            if type(ch) != FunctionDeclaration \
               and type(ch) != FunctionDefinition:
                continue

            f = ch.function

            if not f.static:
                continue

            try:
                prev_ch = func_dec[f]
            except KeyError:
                func_dec[f] = ch
                continue

            # TODO: check for loops in references, the cases in which forward
            #declarations is really needed.

            if type(ch) == FunctionDeclaration:
                self.remove_dup_chunk(prev_ch, ch)
            elif type(ch) == type(prev_ch):
                # prev_ch and ch are FunctionDefinition
                self.remove_dup_chunk(prev_ch, ch)
            else:
                # prev_ch is FunctionDeclaration but ch is FunctionDefinition
                self.remove_dup_chunk(ch, prev_ch)
                func_dec[f] = ch

    def generate(self, writer, gen_debug_comments=False, 
                 append_nl_after_headers = True):
        self.remove_chunks_with_same_origin([
            HeaderInclusion,
            VariableDefinition,
            VariableDeclaration,
            FunctionDeclaration,
            FunctionDefinition,
            StructureDeclaration,
            StructureDeclarationBegin,
            MacroDefinition,
            PointerTypeDeclaration,
            PointerVariableDeclaration,
            VariableUsage
            ])

        self.check_static_function_declarations()

        self.sort_chunks()

        self.optimize_inclusions()

        # semantic sort
        self.chunks.sort(key = source_chunk_key)

        self.sort_chunks()

        writer.write("""
/* {}.{} */
""".format(
    self.name,
    "h" if self.is_header else "c"
    )
            )

        if self.is_header:
            writer.write("""\
#ifndef INCLUDE_{name}_H
#define INCLUDE_{name}_H
""".format(name = self.name.upper()))

        prev_header = False

        for chunk in self.chunks:

            if isinstance(chunk, HeaderInclusion):
                prev_header = True
            else:
                if append_nl_after_headers and prev_header:
                    writer.write("\n")
                prev_header = False

            chunk.check_cols_fix_up()

            if gen_debug_comments:
                writer.write("/* source chunk {} */\n".format(chunk.name))
            writer.write(chunk.code)

        if self.is_header:
            writer.write("""\
#endif /* INCLUDE_{}_H */
""".format(self.name.upper()))

class HeaderFile(SourceFile):
    def __init__(self, name):
        super(HeaderFile, self).__init__(name = name, is_header=True)

#Source tree container

class SourceTreeContainer(object):
    current = None

    def __init__(self):
        self.reg_header = {}
        self.reg_type = {}

    def type_lookup(self, name):
        if not name in self.reg_type:
            raise TypeNotRegistered("Type with name %s is not registered"
                % name)
        return self.reg_type[name]

    def type_exists(self, name):
        try:
            self.type_lookup(name)
            return True
        except TypeNotRegistered:
            return False

    def header_lookup(self, path):
        if not path in self.reg_header:
            raise Exception("Header with path %s is not registered"
                % path)
        return self.reg_header[path]

    def gen_header_inclusion_dot_file(self, dot_file_name):
        dot_writer = open(dot_file_name, "w")

        dot_writer.write("""\
digraph HeaderInclusion {
    node [shape=polygon fontname=Monospace]
    edge[style=filled]

""")

        def _header_path_to_node_name(path):
            return path.replace(".", "_").replace("/", "__").replace("-", "_")

        dot_writer.write("    /* Header nodes: */\n")
        for h in  self.reg_header.values():
            node = _header_path_to_node_name(h.path)
            dot_writer.write('    %s [label="%s"]\n' % (node, h.path))

        dot_writer.write("\n    /* Header dependencies: */\n")

        for h in self.reg_header.values():
            h_node = _header_path_to_node_name(h.path)
            for i in h.inclusions.values():
                i_node = _header_path_to_node_name(i.path)

                dot_writer.write('    %s -> %s\n' % (i_node, h_node))

        dot_writer.write("}\n")

        dot_writer.close()

    def load_header_db(self, list_headers):
        # Create all headers
        for dict_h in list_headers:
            path = dict_h["path"]
            if not path in self.reg_header:
                Header(
                       path = dict_h["path"],
                       is_global = dict_h["is_global"])
            else:
                # Check if existing header equals the one from database?
                pass

        # Set up inclusions
        for dict_h in list_headers:
            path = dict_h["path"]
            h = self.header_lookup(path)

            for inc in dict_h["inclusions"]:
                i = self.header_lookup(inc)
                h.add_inclusion(i)

            for m in dict_h["macros"]:
                h.add_type(Macro.new_from_dict(m))

    def create_header_db(self):
        list_headers = []
        for h in self.reg_header.values():
            dict_h = {}
            dict_h["path"] = h.path
            dict_h["is_global"] = h.is_global

            inc_list = []
            for i in h.inclusions.values():
                inc_list.append(i.path)
            dict_h["inclusions"] = inc_list

            macro_list = []
            for t in h.types.values():
                if type(t) == Macro:
                    macro_list.append(t.gen_dict())
            dict_h["macros"] = macro_list

            list_headers.append(dict_h)

        return list_headers

    def set_cur_stc(self):
        Header.reg = self.reg_header
        Type.reg = self.reg_type

        previous = SourceTreeContainer.current
        SourceTreeContainer.current = self
        return previous

SourceTreeContainer().set_cur_stc()
