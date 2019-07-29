__all__ = [
    "Source"
      , "Header"
  , "AddTypeRefToDefinerException"
  , "TypeNotRegistered"
  , "Type"
      , "TypeReference"
      , "Structure"
      , "Function"
      , "Pointer"
      , "Macro"
      , "MacroType"
      , "Enumeration"
      , "EnumerationElement"
  , "Initializer"
  , "Variable"
  , "SourceChunk"
      , "HeaderInclusion"
      , "MacroDefinition"
      , "PointerTypeDeclaration"
      , "FunctionPointerTypeDeclaration"
      , "MacroTypeUsage"
      , "PointerVariableDeclaration"
      , "FunctionPointerDeclaration"
      , "VariableDeclaration"
      , "VariableDefinition"
      , "StructureForwardDeclaration"
      , "StructureDeclarationBegin"
      , "StructureDeclarationEnd"
      , "StructureTypedefDeclarationBegin"
      , "StructureTypedefDeclarationEnd"
      , "FunctionDeclaration"
      , "FunctionDefinition"
      , "EnumerationElementDeclaration"
  , "SourceFile"
  , "SourceTreeContainer"
  , "TypeReferencesVisitor"
  , "NodeVisitor"
  , "ANC"
  , "CAN"
  , "NBS"
  , "NSS"
]

from os import (
    listdir
)
from os.path import (
    basename,
    splitext,
    join,
    isdir,
    dirname
)
from copy import (
    copy
)
import sys

from re import (
    compile
)
from itertools import (
    chain
)
from common import (
    ee,
    path2tuple,
    pypath,
    OrderedSet,
    ObjectVisitor,
    BreakVisiting
)

with pypath("..ply"):
    # PLY`s C preprocessor is used for several QEMU code analysis
    from ply.lex import (
        lex
    )
    from ply.cpp import (
        Preprocessor,
        literals,
        tokens,
        t_error
    )
    exec("from ply.cpp import t_" + ", t_".join(tokens))

from itertools import (
    count
)
from six import (
    add_metaclass,
    string_types,
    text_type,
    binary_type
)
from collections import (
    defaultdict,
    OrderedDict
)
from .tools import (
    get_cpp_search_paths
)
from collections import (
    deque
)


# List of coding style specific code generation settings.

# Pointers are automatically re-directed to declarations of types if available.
POINTER_TO_DECLARATION = ee("QDT_POINTER_TO_DECLARATION", "True")

# Reduces amount of #include directives
OPTIMIZE_INCLUSIONS = ee("QDT_OPTIMIZE_INCLUSIONS", "True")

# Skip global headers inclusions. All needed global headers included in
# "qemu/osdep.h".
SKIP_GLOBAL_HEADERS = ee("QDT_SKIP_GLOBAL_HEADERS", "True")


# Used for sys.stdout recovery
sys_stdout_recovery = sys.stdout

macro_forbidden = compile("[^0-9A-Z_]")

ANC = "@a" # indent anchor
CAN = "@c" # cancel indent anchor
NBS = "@b" # non-breaking space
NSS = "@s" # non-slash space
common_re = "(?<!@)((?:@@)*)(%s)"
re_anc = compile(common_re % ANC)
re_can = compile(common_re % CAN)
re_nbs = compile(common_re % NBS)
re_nss = compile(common_re % NSS)
re_clr = compile("@(.|$)")


APPEND_NL_AFTER_MACROS = not ee("QDT_NO_NL_AFTER_MACROS")


# Code generation model
class ChunkGenerator(object):
    """ Maintains context of source code chunks generation process. """

    def __init__(self, definer):
        self.chunk_cache = { definer: [] }
        self.for_header = isinstance(definer, Header)
        """ Tracking of recursive calls of `provide_chunks`. Currently used
        only to generate "extern" keyword for global variables in header and to
        distinguish structure fields and normal variables. """
        self.stack = []

    def provide_chunks(self, origin, **kw):
        """ Given origin the method returns chunk list generating it on first
        access. """
        if isinstance(origin, TypeReference):
            key = origin.type.definer
        else:
            key = origin

        try:
            chunks = self.chunk_cache[key]
        except KeyError:
            # Notify user about cycle dependency and continue
            if isinstance(origin, Type) and origin.is_named:
                for frame in self.stack:
                    if not isinstance(frame, Type):
                        continue
                    if frame.is_named and frame.name == origin.name:
                        print("Chunks providing process cycled"
                            " on\n    %s %s\nStack:\n%s" % (
                                type(origin).__name__, origin.name,
                                self.stringify_stack()
                            )
                        )
                        return []

            self.stack.append(origin)

            if isinstance(origin, Function):
                if (    self.for_header
                    and (not origin.static or not origin.inline)
                ):
                    chunks = origin.gen_declaration_chunks(self, **kw)
                else:
                    chunks = origin.gen_definition_chunks(self, **kw)
            elif isinstance(origin, Variable):
                # A variable in a header does always have `extern` modifier.
                # Note that some "variables" do describe `struct` entries and
                # must not have it.
                if len(self.stack) == 1:
                    if self.for_header:
                        kw["extern"] = True
                        chunks = origin.gen_declaration_chunks(self, **kw)
                    else:
                        chunks = origin.get_definition_chunks(self, **kw)
                else:
                    if isinstance(self.stack[-2], Structure):
                        # structure fields
                        chunks = origin.gen_declaration_chunks(self, **kw)
                    elif (
                        # Generate a header inclusion for global variable
                        # from other module.
                        # This code assumes that the variable (`origin`) is
                        # used by a function (`self.stack[-2]`) because there
                        # is no other entities whose can use a variable.
                        # XXX: One day an `Initializer` will do it.
                        origin.declarer is not None
                        # Check if chunks are being requested for a file which
                        # is neither the header declares the variable nor the
                        # module defining it.
                    and origin.declarer not in self.stack[-2].get_definers()
                    and origin.definer not in self.stack[-2].get_definers()
                    ):
                        declarer = origin.declarer
                        try:
                            chunks = self.chunk_cache[declarer]
                        except KeyError:
                            chunks = [
                                HeaderInclusion(declarer).add_reason(origin)
                            ]
                    else:
                        # Something like a static inline function in a header
                        # may request chunks for a global variable. This case
                        # the stack height is greater than 1.
                        if self.for_header:
                            kw["extern"] = True
                            chunks = origin.gen_declaration_chunks(self, **kw)
                        else:
                            chunks = origin.get_definition_chunks(self, **kw)
            elif (    SKIP_GLOBAL_HEADERS
                  and isinstance(origin, TypeReference)
                  and self.for_header
                  and origin.type.definer.is_global
            ):
                chunks = []
            else:
                chunks = origin.gen_defining_chunk_list(self, **kw)

            self.stack.pop()

            # Note that conversion to a tuple is performed to prevent further
            # modifications of chunk list.
            self.chunk_cache[key] = tuple(chunks)
        else:
            if isinstance(origin, TypeReference):
                if chunks:
                    # It's HeaderInclusion
                    chunks[0].add_reason(origin.type)
                # else:
                #     print("reference to %s provided no inclusion" % origin)

        return chunks

    def get_all_chunks(self):
        res = set()

        for chunks in self.chunk_cache.values():
            for chunk in chunks:
                if chunk not in res:
                    res.add(chunk)

        return list(res)

    def stringify_stack(self):
        frames = deque()
        for frame in self.stack:
            definer = None

            try:
                if isinstance(frame, TypeReference):
                    definer = frame.type.definer.path
                elif isinstance(frame, Type):
                    definer = frame.definer.path
            except AttributeError:
                pass

            definer = "" if definer is None else ("  (%s)" % definer)

            frames.append("    %-20s %s%s" % (
                type(frame).__name__, frame, definer
            ))
        return "\n".join(frames)

# Source code models


class Source(object):

    def __init__(self, path):
        self.path = path
        self.types = {}
        self.inclusions = {}
        self.global_variables = {}
        self.references = set()
        self.protection = False

    def add_reference(self, ref):
        if not isinstance(ref, Type) and not isinstance(ref, Variable):
            raise ValueError("Trying to add source reference which is not a"
                " type"
            )
        if isinstance(ref, TypeReference):
            raise ValueError("Source reference may not be TypeReference."
                "Only original types are allowed."
            )
        self.references.add(ref)

        return self

    def add_references(self, refs):
        for ref in refs:
            self.add_reference(ref)

        return self

    def add_global_variable(self, var):
        if var.name in self.global_variables:
            raise RuntimeError("Variable with name %s is already in file %s"
                % (var, self.name)
            )

        fixer = TypeFixerVisitor(self, var).visit()

        # Auto add references to types this variable does depend on
        self.add_references(tr.type for tr in fixer.new_type_references)
        # Auto add definers for types used by variable initializer
        if type(self) is Source: # exactly a module, not a header
            if var.definer is not None:
                raise RuntimeError(
                    "Variable '%s' is already defined in '%s'" % (
                        var, self.path
                    )
                )
            if var.initializer is not None:
                for t in var.initializer.used_types:
                    for s in t.get_definers():
                        if s == self:
                            continue
                        if not isinstance(s, Header):
                            raise RuntimeError("Attempt to define variable"
                                " {var} whose initializer code uses type {t}"
                                " defined in non-header file {file}".format(
                                var = var,
                                t = t,
                                file = s.path
                            ))

            var.definer = self
        elif type(self) is Header: # exactly a header
            if var.declarer is not None:
                raise RuntimeError(
                    "Variable '%s' is already declared by '%s'" % (
                        var, self.path
                    )
                )
            var.declarer = self

        self.global_variables[var.name] = var

        return self

    def add_inclusion(self, header):
        if not isinstance(header, Header):
            raise ValueError(
"Inclusion of a non-header file is forbidden (%s)" % header.path
            )

        if header.path not in self.inclusions:
            self.inclusions[header.path] = header

            for t in header.types.values():
                try:
                    if isinstance(t, TypeReference):
                        self._add_type_recursive(TypeReference(t.type))
                    else:
                        self._add_type_recursive(TypeReference(t))
                except AddTypeRefToDefinerException:
                    # inclusion cycles will cause this exceptions
                    pass

            if self in header.includers:
                raise RuntimeError("Header %s is among includers of %s but"
                    " does not includes it" % (self.path, header.path)
                )

            header.includers.append(self)

        return self

    def _add_type_recursive(self, type_ref):
        # adding a type may satisfy a dependency
        if type_ref.type in self.references:
            self.references.remove(type_ref.type)

        if type_ref.name in self.types:
            t = self.types[type_ref.name]
            if isinstance(t, TypeReference):
                # To check incomplete type case
                if not t.type.definer == type_ref.type.definer:
                    raise RuntimeError("Conflict reference to type %s found in"
                        " source %s. The type is defined both in %s and %s"
                        % (t, self.path, type_ref.type.definer.path,
                            t.type.definer.path
                        )
                    )
            # To make more conflicts checking
            return False

        self.types[type_ref.name] = type_ref
        return True

    def add_types(self, types):
        for t in types:
            self.add_type(t)

        return self

    def add_type(self, _type):
        if isinstance(_type, TypeReference):
            raise ValueError("A type reference (%s) cannot be added to a"
                " source (%s) externally" % (_type, self.path)
            )

        _type.definer = self
        self.types[_type.name] = _type

        fixer = TypeFixerVisitor(self, _type).visit()

        # Auto add references to types this one does depend on
        self.add_references(tr.type for tr in fixer.new_type_references)

        # Addition of a required type does satisfy the dependence.
        if _type in self.references:
            self.references.remove(_type)

        return self

    def gen_chunks(self, inherit_references = False):
        """ In some use cases header should not satisfy references of its
inclusions by itself. Instead, it must inherit them. A source file must
satisfy the references in such case. Set inherit_references to True for
switching to that mode.
        """

        if inherit_references:
            assert(isinstance(self, Header))

        ref_list = []

        if isinstance(self, Header):
            for user in self.includers:
                for ref in user.references:
                    if ref.definer not in user.inclusions:
                        ref_list.append(TypeReference(ref))

        TypeFixerVisitor(self, self.global_variables).visit()

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

                if TypeFixerVisitor(self, t).visit().replaced:
                    replaced = True

            if not replaced:
                break
            # Preserve current types list. See the comment above.
            l = list(self.types.values()) + ref_list

        gen = ChunkGenerator(self)

        for t in self.types.values():
            if isinstance(t, TypeReference):
                continue

            if t.definer is not self:
                raise RuntimeError("Type %s is defined in %s but presented in"
" %s not by a reference." % (t, t.definer.path, self.path)
                )

            gen.provide_chunks(t)

        for gv in self.global_variables.values():
            gen.provide_chunks(gv)

        if isinstance(self, Header):
            for r in ref_list:
                gen.provide_chunks(r)

        chunks = gen.get_all_chunks()

        # Account extra references
        chunk_cache = {}

        # Build mapping
        for ch in chunks:
            origin = ch.origin
            chunk_cache.setdefault(origin, []).append(ch)

        # link chunks
        for ch in chunks:
            origin = ch.origin

            """ Any object that could be an origin of chunk may provide an
iterable container of extra references. A reference must be another origin.
Chunks originated from referencing origin are referenced to chunks originated
from each referenced origin.

    Extra references may be used to apply extended (semantic) order when syntax
order does not meet all requirements.
            """
            try:
                refs = origin.extra_references
            except AttributeError:
                continue

            for r in refs:
                try:
                    referenced_chunks = chunk_cache[r]
                except KeyError:
                    # no chunk was generated for that referenced origin
                    continue

                ch.add_references(referenced_chunks)

        return chunks

    def generate(self, inherit_references = False):
        Header.propagate_references()

        file = SourceFile(self, protection = self.protection)

        file.add_chunks(self.gen_chunks(inherit_references))

        return file


class CPP(object):
    "This class used as definer for CPPMacro"
    references = set()


class AddTypeRefToDefinerException(RuntimeError):
    pass


class ParsePrintFilter(object):

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


# A Py version independent way to add metaclass.
# https://stackoverflow.com/questions/39013249/metaclass-in-python3-5
@add_metaclass(registry)
class Header(Source):
    reg = {}

    @staticmethod
    def _on_include(includer, inclusion, is_global):
        if path2tuple(inclusion) not in Header.reg:
            print("Info: parsing " + inclusion + " as inclusion")
            h = Header(path = inclusion, is_global = is_global)
            h.parsed = True
        else:
            h = Header[inclusion]

        Header[includer].add_inclusion(h)

    @staticmethod
    def _on_define(definer, macro):
        # macro is ply.cpp.Macro

        if "__FILE__" == macro.name:
            return

        h = Header[definer]

        try:
            m = Type[macro.name]
            if not m.definer.path == definer:
                print("Info: multiple definitions of macro %s in %s and %s" % (
                    macro.name, m.definer.path, definer
                ))
        except:
            m = Macro(
                name = macro.name,
                text = "".join(tok.value for tok in macro.value),
                args = (
                    None if macro.arglist is None else list(macro.arglist)
                )
            )
            h.add_type(m)

    @staticmethod
    def _build_inclusions(start_dir, prefix, recursive):
        full_name = join(start_dir, prefix)
        if isdir(full_name):
            if not recursive:
                return
            for entry in listdir(full_name):
                yield Header._build_inclusions(
                    start_dir,
                    join(prefix, entry),
                    True
                )
        else:
            (name, ext) = splitext(prefix)
            if ext == ".h":
                if path2tuple(prefix) not in Header.reg:
                    h = Header(path = prefix, is_global = False)
                    h.parsed = False
                else:
                    h = Header[prefix]

                if not h.parsed:
                    h.parsed = True
                    print("Info: parsing " + prefix)

                    p = Preprocessor(lex())
                    p.add_path(start_dir)

                    global cpp_search_paths
                    for path in cpp_search_paths:
                        p.add_path(path)

                    p.on_include = Header._on_include
                    p.on_define.append(Header._on_define)

                    if sys.version_info[0] == 3:
                        header_input = (
                            open(full_name, "r", encoding = "UTF-8").read()
                        )
                    else:
                        header_input = (
                            open(full_name, "rb").read().decode("UTF-8")
                        )

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

    @staticmethod
    def co_build_inclusions(dname, recursive):
        # Default include search folders should be specified to
        # locate and parse standard headers.
        # parse `cpp -v` output to get actual list of default
        # include folders. It should be cross-platform
        global cpp_search_paths
        cpp_search_paths = get_cpp_search_paths()

        Header.yields_per_header = []

        if not isinstance(sys.stdout, ParsePrintFilter):
            sys.stdout = ParsePrintFilter(sys.stdout)

        for h in Header.reg.values():
            h.parsed = False

        for entry in listdir(dname):
            yield Header._build_inclusions(dname, entry, recursive)

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

    @staticmethod
    def lookup(path):
        tpath = path2tuple(path)

        if tpath not in Header.reg:
            raise RuntimeError("Header with path %s is not registered" % path)
        return Header.reg[tpath]

    def __init__(self, path, is_global = False, protection = True):
        super(Header, self).__init__(path)
        self.is_global = is_global
        self.includers = []
        self.protection = protection

        tpath = path2tuple(path)
        if tpath in Header.reg:
            raise RuntimeError("Header %s is already registered" % path)

        Header.reg[tpath] = self

    def __str__(self):
        if self.is_global:
            return "<%s>" % self.path
        else:
            return '"%s"' % self.path

    def _add_type_recursive(self, type_ref):
        if type_ref.type.definer == self:
            raise AddTypeRefToDefinerException(
"Adding a type reference (%s) to a file (%s) defining the type" % (
    type_ref.type, self.path
)
            )

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
        # key contains of 'g' or 'l' and header path
        # 'g' and 'l' are used to distinguish global and local
        # headers with same
        return hash("{}{}".format(
            "g" if self.is_global else "l",
            self.path
        ))

    @staticmethod
    def _propagate_reference(h, ref):
        h.add_reference(ref)

        for u in h.includers:
            if type(u) is Source: # exactly a module, not a header
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
                    if type(u) is Source: # exactly a module, not a header
                        continue
                    if ref in u.references:
                        continue
                    if ref.name in u.types:
                        continue
                    Header._propagate_reference(u, ref)

# Type models


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
        array_size = None,
        used = False
    ):
        if self.incomplete:
            if not pointer:
                raise ValueError("Cannot create non-pointer variable %s"
                    " of incomplete type %s." % (name, self)
                )

        if pointer:
            return Variable(name, Pointer(self),
                initializer = initializer,
                static = static,
                array_size = array_size,
                used = used
            )
        else:
            return Variable(name, self,
                initializer = initializer,
                static = static,
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
        if not isinstance(other, Type):
            return NotImplemented
        return self.name < other.name


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

        if _type.is_named:
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

    def __init__(self, name, *fields):
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
        decl = Structure(self.name + ".declaration")
        self.declaration = decl
        decl._definition = self
        return decl

    def __getattr__(self, name):
        "Tries to find undefined attributes among fields."
        d = self.__dict__
        try:
            return d[name]
        except KeyError:
            try:
                return d["_fields"][name]
            except KeyError:
                return super(Structure, self).__getattr__(name)

    def get_definers(self):
        if self.definer is None:
            raise RuntimeError("Getting definers for structure %s that is not"
                " added to a source", self
            )

        definers = [self.definer]

        for f in self.fields.values():
            definers.extend(f.get_definers())

        return definers

    def append_field(self, variable):
        v_name = variable.name
        if v_name in self.fields:
            raise RuntimeError("A field with name %s already exists in"
                " the structure %s" % (v_name, self)
            )

        self.fields[v_name] = variable

        ForwardDeclarator(variable).visit()

    def append_fields(self, fields):
        for v in fields:
            self.append_field(v)

    def append_field_t(self, _type, name, pointer = False):
        self.append_field(_type(name, pointer = pointer))

    def append_field_t_s(self, type_name, name, pointer = False):
        self.append_field_t(Type[type_name], name, pointer)

    def gen_chunks(self, generator):
        fields_indent = "    "
        indent = ""

        if self._definition is not None:
            return [StructureForwardDeclaration(self, indent)]

        if self.declaration is None:
            struct_begin = StructureTypedefDeclarationBegin(self, indent)
            struct_end = StructureTypedefDeclarationEnd(self, fields_indent,
                indent, True
            )
        else:
            struct_begin = StructureDeclarationBegin(self, indent)
            struct_end = StructureDeclarationEnd(self, fields_indent,
                indent, True
            )

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

        field_indent = indent + fields_indent
        field_refs = []
        top_chunk = struct_begin

        for f in self.fields.values():
            # Note that 0-th chunk is field and rest are its dependencies
            decl_chunks = generator.provide_chunks(f, indent = field_indent)

            field_declaration = decl_chunks[0]

            field_refs.extend(list(field_declaration.references))
            field_declaration.clean_references()
            field_declaration.add_reference(top_chunk)
            top_chunk = field_declaration

        struct_begin.add_references(field_refs)
        struct_end.add_reference(top_chunk)

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
            return ["fields"]
        else:
            return []

    def __c__(self, writer):
        writer.write(self.c_name)


class Enumeration(Type):

    def __init__(self, type_name, elems_dict, enum_name = ""):
        super(Enumeration, self).__init__(name = type_name)

        self.elems = []
        self.enum_name = enum_name
        t = [ Type["int"] ]
        for key, val in elems_dict.items():
            self.elems.append(
                EnumerationElement(self, key, Initializer(str(val), t))
            )

        self.elems.sort(key = lambda x: int(x.initializer.code))

    def __getattr__(self, name):
        "Tries to find undefined attributes among elems."
        d = self.__dict__
        try:
            return d[name]
        except KeyError:
            for e in self.elems:
                if name == e.name:
                    return e
            else:
                return super(Enumeration, self).__getattr__(name)

    def gen_chunks(self, generator):
        fields_indent = "    "
        indent = ""

        enum_begin = EnumerationDeclarationBegin(self, indent)
        enum_end = EnumerationDeclarationEnd(self, indent)

        field_indent = indent + fields_indent
        field_refs = []
        top_chunk = enum_begin

        for f in self.elems:
            field_declaration = EnumerationElementDeclaration(f,
                indent = field_indent,
                separ = "" if f == self.elems[-1] else ","
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

        for f in self.elems:
            definers.extend(f.get_definers())

        return definers

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
        const: pointer to constant (not a constant pointer).
        """
        super(Pointer, self).__init__(name = name, incomplete = False)

        # define c_name for nameless pointers
        if not self.is_named:
            c_name = _type.c_name + '*'
            if const:
                c_name = "const@b" + c_name
            self.c_name = c_name

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

        """ 'typedef' does not require refererenced types to be visible.
Hence, it is not correct to add references to the PointerTypeDeclaration
chunk. The references is to be added to `users` of the 'typedef'.
    """
        ch.add_references(refs)

        return [ch]

    def __hash__(self):
        stars = "*"
        t = self.type
        while isinstance(t, Pointer) and not t.is_named:
            t = t.type
            stars += "*"
        return hash(hash(t) + hash(stars))

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
        return MacroType(self, initializer = macro_initializer)(name,
            pointer = pointer,
            initializer = initializer,
            static = static,
            array_size = array_size,
            used = used
        )

    def gen_usage(self, initializer = None, name = None):
        return MacroType(self,
            initializer = initializer,
            name = name,
            is_usage = True
        )

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


class MacroType(Type):
    def __init__(self, _macro,
        initializer = None,
        name = None,
        is_usage = False
    ):
        if not isinstance(_macro, Macro):
            raise ValueError("Attempt to create macrotype from "
                " %s which is not macro." % _macro
            )

        if is_usage and name is None:
            name = _macro.name + ".usage" + str(id(self))

        super(MacroType, self).__init__(name = name, incomplete = False)

        # define c_name for nameless macrotypes
        if not self.is_named:
            self.c_name = _macro.gen_usage_string(initializer)

        self.macro = _macro
        self.initializer = initializer

    def get_definers(self):
        if self.is_named:
            return super(MacroType, self).get_definers()
        else:
            return self.macro.get_definers()

    def gen_chunks(self, generator, indent = ""):
        macro = self.macro
        initializer = self.initializer

        refs = list(generator.provide_chunks(macro))

        if initializer is not None:
            for v in initializer.used_variables:
                """ Note that 0-th chunk is variable and rest are its
                dependencies """
                refs.append(generator.provide_chunks(v)[0])

            for t in initializer.used_types:
                refs.extend(generator.provide_chunks(t))

        if self.is_named:
            ch = MacroTypeUsage(macro, initializer, indent)
            ch.add_references(refs)
            return [ch]
        else:
            return refs

    def __str__(self):
        if self.is_named:
            return super(MacroType, self).__str__()
        else:
            return "macro type from %s" % self.macro

    __type_references__ = ["macro", "initializer"]


class CPPMacro(Macro):
    """ A kind of macro defined by the C preprocessor.
    For example __FILE__, __LINE__, __FUNCTION__ and etc.
    """

    def __init__(self, *args, **kw):
        super(CPPMacro, self).__init__(*args, **kw)
        self.definer = CPP

    def gen_chunks(self, _):
        # CPPMacro does't require referenced types
        # because it's defined by C preprocessor.
        return []


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
        "String of * required to full dereference of this as a pointer."
        res = ""

        t = self.type
        while isinstance(t, Pointer):
            res += "*"
            t = t.type

        return res

    @property
    def full_deref(self):
        t = self.type
        while isinstance(t, Pointer):
            t = t.type
        return t

    def gen_declaration_chunks(self, generator,
        indent = "",
        extern = False
    ):
        if isinstance(self.type, Pointer) and not self.type.is_named:
            if isinstance(self.type.type, Function):
                ch = FunctionPointerDeclaration(self, indent, extern)
                refs = gen_function_decl_ref_chunks(self.type.type, generator)
            else:
                ch = PointerVariableDeclaration(self, indent, extern)
                refs = generator.provide_chunks(self.type.type)
            ch.add_references(refs)
        else:
            ch = VariableDeclaration(self, indent, extern)
            refs = generator.provide_chunks(self.type)
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
                """ Note that 0-th chunk is variable and rest are its
                dependencies """
                refs.append(generator.provide_chunks(v)[0])

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

    __type_references__ = ["type", "initializer"]

# Type inspecting


class TypeFixerVisitor(TypeReferencesVisitor):

    def __init__(self, source, type_object):
        super(TypeFixerVisitor, self).__init__(type_object)

        self.source = source
        self.replaced = False
        self.new_type_references = deque()

    def replace(self, new_value):
        self.replaced = True
        super(TypeFixerVisitor, self).replace(new_value)

    def on_visit(self):
        if isinstance(self.cur, Type):
            t = self.cur
            if isinstance(t, TypeReference):
                try:
                    self_tr = self.source.types[t.name]
                except KeyError:
                    # The source does not have such type reference
                    self_tr = TypeReference(t.type)
                    self.source.types[t.name] = self_tr
                    self.new_type_references.append(self_tr)

                if self_tr is not t:
                    self.replace(self_tr)

                raise BreakVisiting()

            if t.base:
                raise BreakVisiting()

            """ Skip pointer and macrotype types without name. Nameless pointer
            or macrotype does not have definer and should not be replaced with
            type reference """
            if isinstance(t, (Pointer, MacroType)) and not t.is_named:
                return

            # Add definerless types to the Source automatically
            if t.definer is None:
                if t.is_named:
                    self.source.add_type(t)
                return

            if t.definer is self.source:
                return

            # Make TypeReference to declaration instead of definition:
            # In a case when a declaration and a definition are in
            # different files, it is necessary to include the file with
            # the declaration
            if isinstance(t, Function) and t.declaration is not None:
                t = t.declaration
                if type(t) is TypeReference:
                    t = t.type

            # replace foreign type with reference to it
            try:
                tr = self.source.types[t.name]
            except KeyError:
                tr = TypeReference(t)
                self.source.types[t.name] = tr
                self.new_type_references.append(tr)

            self.replace(tr)

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
            or (isinstance(t, (Pointer, MacroType)) and not t.is_named)
        ):
            new_t = copy(t)

            self.replace(new_t, skip_trunk = False)
        else:
            raise BreakVisiting()

# Source code instances


class SourceChunk(object):
    """
`weight` is used during coarse chunk sorting. Chunks with less `weight` value
    are moved to the top of the file. Then all chunks are ordered topologically
    (with respect to inter-chunk references). But chunks which is not linked
    by references will preserve `weight`-based order.
    """
    weight = 5

    def __init__(self, origin, name, code, references = None):
        self.origin = origin
        self.name = name
        self.code = code
        # visited is used during depth-first sort
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

    def check_cols_fix_up(self, max_cols = 80, indent = "    "):
        lines = self.code.split('\n')
        code = ""
        last_line = len(lines) - 1

        for idx1, line in enumerate(lines):
            if idx1 == last_line and len(line) == 0:
                break;

            clear_line = re_clr.sub("\\1", re_anc.sub("\\1", re_can.sub("\\1",
                         re_nbs.sub("\\1 ", re_nss.sub("\\1 ", line)))))

            if len(clear_line) <= max_cols:
                code += clear_line + '\n'
                continue

            line_no_indent_len = len(line) - len(line.lstrip(' '))
            line_indent = line[:line_no_indent_len]
            indents = []
            indents.append(len(indent))
            tmp_indent = indent

            """
            1. cut off indent of the line
            2. surround non-slash spaces with ' ' moving them to separated
               words
            3. split the line onto words
            4. replace any non-breaking space with a regular space in each word
            """
            words = list(filter(None, map(
                lambda a: re_nbs.sub("\\1 ", a),
                re_nss.sub("\\1 " + NSS + ' ', line.lstrip(' ')).split(' ')
            )))

            ll = 0 # line length
            last_word = len(words) - 1
            for idx2, word in enumerate(words):
                if word == NSS:
                    slash = False
                    continue

                """ split the word onto anchor control sequences and n-grams
                around them """
                subwords = list(filter(None, chain(*map(
                    lambda a: re_can.split(a),
                    re_anc.split(word)
                ))))
                word = ""
                subword_indents = []
                for subword in subwords:
                    if subword == ANC:
                        subword_indents.append(len(word))
                    elif subword == CAN:
                        if subword_indents:
                            subword_indents.pop()
                        else:
                            try:
                                indents.pop()
                            except IndexError:
                                raise RuntimeError("Trying to pop indent"
                                    " anchor from empty stack"
                                )
                    else:
                        word += re_clr.sub("\\1", subword)

                if ll > 0:
                    # The variable r reserves characters for " \\"
                    # that can be added after current word
                    if idx2 == last_word or words[idx2 + 1] == NSS:
                        r = 0
                    else:
                        r = 2
                    """ If the line will be broken _after_ this word,
its length may be still longer than max_cols because of safe breaking (' \').
If so, brake the line _before_ this word. Safe breaking is presented by
'r' variable in the expression which is 0 if safe breaking is not required
after this word.
                    """
                    if ll + 1 + len(word) + r > max_cols:
                        if slash:
                            code += " \\"
                        code += '\n' + line_indent + tmp_indent + word
                        ll = len(line_indent) + len(tmp_indent) + len(word)
                    else:
                        code += ' ' + word
                        ll += 1 + len(word)
                else:
                    code += line_indent + word
                    ll += len(line_indent) + len(word)

                word_indent = ll - len(line_indent) - len(word)
                for ind in subword_indents:
                    indents.append(word_indent + ind)
                tmp_indent = " " * indents[-1] if indents else ""
                slash = True

            code += '\n'

        self.code = '\n'.join(map(lambda a: a.rstrip(' '), code.split('\n')))

    def __lt__(self, other):
        sw = type(self).weight
        ow = type(other).weight
        if sw < ow:
            return True
        elif sw > ow:
            return False
        else:
            return self.name < other.name


class HeaderInclusion(SourceChunk):
    weight = 0

    def __init__(self, header):
        super(HeaderInclusion, self).__init__(header,
            "Header %s inclusion" % header.path,
            "",
            references = []
        )
        self._path = None
        self.path = path2tuple(header.path)
        self.reasons = OrderedSet()

    def add_reason(self, _type, kind = "defines"):
        self.reasons.add((kind, _type))
        return self

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, _path):
        if self._path == _path:
            return

        self._path = _path

        self.code = """\
#include {lq}{path}{rq}
""".format(
    lq = "<" if self.origin.is_global else '"',
    # Always use UNIX path separator in `#include` directive.
    path = "/".join(_path),
    rq = ">" if self.origin.is_global else '"'
        )

    def __lt__(self, other):
        """ During coarse chunk sorting <global> header inclusions are moved to
        the top of "local". Same headers are ordered by path. """
        if isinstance(other, HeaderInclusion):
            shdr = self.origin
            ohdr = other.origin

            sg = shdr.is_global
            og = ohdr.is_global
            if sg == og:
                return shdr.path < ohdr.path
            else:
                # If self `is_global` flag is greater then order weight is less
                return sg > og
        else:
            return super(HeaderInclusion, self).__lt__(other)


class MacroDefinition(SourceChunk):
    weight = 1

    def __init__(self, macro, indent = ""):
        if macro.args is None:
            args_txt = ""
        else:
            args_txt = '('
            for a in macro.args[:-1]:
                args_txt += a + ", "
            args_txt += macro.args[-1] + ')'

        super(MacroDefinition, self).__init__(macro,
            "Definition of macro %s" % macro,
            "%s#define %s%s%s" % (
                indent,
                macro.c_name,
                args_txt,
                "" if macro.text is None else (" %s" % macro.text)
            )
        )


class PointerTypeDeclaration(SourceChunk):

    def __init__(self, _type, def_name):
        self.def_name = def_name

        super(PointerTypeDeclaration, self).__init__(_type,
            "Definition of pointer to type %s" % _type,
            "typedef@b" + _type.c_name + "@b" + def_name + ";\n"
        )


class FunctionPointerTypeDeclaration(SourceChunk):

    def __init__(self, _type, def_name):
        self.def_name = def_name

        super(FunctionPointerTypeDeclaration, self).__init__(_type,
            "Definition of function pointer type %s" % _type,
            ("typedef@b"
              + gen_function_declaration_string("", _type,
                    pointer_name = def_name
                )
              + ";\n"
            )
        )


class MacroTypeUsage(SourceChunk):

    def __init__(self, macro, initializer, indent):
        self.macro = macro
        self.initializer = initializer

        super(MacroTypeUsage, self).__init__(macro,
            "Usage of macro type %s" % macro,
            code = indent + macro.gen_usage_string(initializer)
        )


class PointerVariableDeclaration(SourceChunk):

    def __init__(self, var, indent = "", extern = False):
        t = var.type.type
        super(PointerVariableDeclaration, self).__init__(var,
            "Declaration of pointer %s to type %s" % (var, t),
            """\
{indent}{extern}{const}{type_name}@b*{var_name};
""".format(
    indent = indent,
    const = "const@b" if var.const else "",
    type_name = t.c_name,
    var_name = var.name,
    extern = "extern@b" if extern else ""
            )
        )


class FunctionPointerDeclaration(SourceChunk):

    def __init__(self, var, indent = "", extern = False):
        t = var.type.type
        super(FunctionPointerDeclaration, self).__init__(var,
            "Declaration of pointer %s to function %s" % (var, t),
            """\
{indent}{extern}{decl_str};
""".format(
    indent = indent,
    extern = "extern@b" if extern else "",
    decl_str = gen_function_declaration_string("", t,
        pointer_name = var.name,
        array_size = var.array_size
    )
            )
        )


class VariableDeclaration(SourceChunk):
    weight = 4

    def __init__(self, var, indent = "", extern = False):
        super(VariableDeclaration, self).__init__(var,
            "Variable %s of type %s declaration" % (var, var.type),
            """\
{indent}{extern}{const}{type_name}@b{var_name}{array_decl};
""".format(
    indent = indent,
    const = "const@b" if var.const else "",
    type_name = var.type.c_name,
    var_name = var.name,
    array_decl = gen_array_declaration(var.array_size),
    extern = "extern@b" if extern else ""
            )
        )


class VariableDefinition(SourceChunk):
    weight = 5

    def __init__(self, var,
        indent = "",
        append_nl = True,
        separ = ";"
    ):
        super(VariableDefinition, self).__init__(var,
            "Variable %s of type %s definition" % (var, var.type),
            """\
{indent}{static}{const}{type_name}{var_name}{array_decl}{used}{init}{separ}{nl}
""".format(
    indent = indent,
    static = "static@b" if var.static else "",
    const = "const@b" if var.const else "",
    type_name = var.type.c_name + "@b",
    var_name = var.name,
    array_decl = gen_array_declaration(var.array_size),
    used = "" if var.used else "@b__attribute__((unused))",
    init = gen_init_string(var.type, var.initializer, indent),
    separ = separ,
    nl = "\n" if append_nl else ""
            )
        )


class StructureForwardDeclaration(SourceChunk):

    def __init__(self, struct, indent = "", append_nl = True):
        super(StructureForwardDeclaration, self).__init__(struct,
            "Structure %s forward declaration" % struct,
            """\
{indent}typedef@bstruct@b{struct_name}@b{struct_name};{nl}
""".format(
    indent = indent,
    struct_name = struct.c_name,
    nl = "\n" if append_nl else ""
            )
        )


class StructureTypedefDeclarationBegin(SourceChunk):

    def __init__(self, struct, indent):
        super(StructureTypedefDeclarationBegin, self).__init__(struct,
            "Beginning of structure %s declaration" % struct,
            """\
{indent}typedef@bstruct@b{struct_name}@b{{
""".format(
    indent = indent,
    struct_name = struct.c_name
            )
        )


class StructureTypedefDeclarationEnd(SourceChunk):
    weight = 2

    def __init__(self, struct,
        fields_indent = "    ",
        indent = "",
        append_nl = True
    ):
        super(StructureTypedefDeclarationEnd, self).__init__(struct,
            "Ending of structure %s declaration" % struct,
            """\
{indent}}}@b{struct_name};{nl}
""".format(
    indent = indent,
    struct_name = struct.c_name,
    nl = "\n" if append_nl else ""
            )
        )


class StructureDeclarationBegin(SourceChunk):

    def __init__(self, struct, indent):
        super(StructureDeclarationBegin, self).__init__(struct,
            "Beginning of structure %s declaration" % struct,
            """\
{indent}struct@b{struct_name}@b{{
""".format(
    indent = indent,
    struct_name = struct.c_name
            )
        )


class StructureDeclarationEnd(SourceChunk):
    weight = 2

    def __init__(self, struct,
        fields_indent = "    ",
        indent = "",
        append_nl = True
    ):
        super(StructureDeclarationEnd, self).__init__(struct,
            "Ending of structure %s declaration" % struct,
            """\
{indent}}};{nl}
""".format(
    indent = indent,
    nl = "\n" if append_nl else ""
            )
        )


class EnumerationDeclarationBegin(SourceChunk):

    def __init__(self, enum, indent = ""):
        super(EnumerationDeclarationBegin, self).__init__(enum,
            "Beginning of enumeration %s declaration" % enum.enum_name,
            """\
{indent}enum@b{enum_name}{{
""".format(
    indent = indent,
    enum_name = enum.enum_name + "@b" if enum.enum_name else ""
            )
        )


class EnumerationDeclarationEnd(SourceChunk):
    weight = 3

    def __init__(self, enum, indent = ""):
        super(EnumerationDeclarationEnd, self).__init__(enum,
            "Ending of enumeration %s declaration" % enum.enum_name,
            """\
{indent}}};\n
""".format(indent = indent)
        )


class EnumerationElementDeclaration(SourceChunk):

    def __init__(self, elem,
        indent = "",
        separ = ","
    ):
        super(EnumerationElementDeclaration, self).__init__(elem,
            "Enumeration element %s declaration" % elem,
            """\
{indent}{name}{init}{separ}
""".format(
    indent = indent,
    name = elem.c_name,
    init = gen_init_string(elem, elem.initializer, indent),
    separ = separ
            )
        )


def gen_array_declaration(array_size):
    if array_size is not None:
        if array_size == 0:
            array_decl = "[]"
        elif array_size > 0:
            array_decl = '[' + str(array_size) + ']'
    else:
        array_decl = ""
    return array_decl


def gen_function_declaration_string(indent, function,
    pointer_name = None,
    array_size = None
):
    if function.args is None:
        args = "void"
    else:
        args = ""
        for a in function.args:
            args += a.type.c_name + "@b" + a.name
            if not a == function.args[-1]:
                args += ",@s"

    return "{indent}{static}{inline}{ret_type}{name}(@a{args}@c)".format(
        indent = indent,
        static = "static@b" if function.static else "",
        inline = "inline@b" if function.inline else "",
        ret_type = function.ret_type.c_name + "@b",
        name = function.c_name if pointer_name is None else (
            "(*" + pointer_name + gen_array_declaration(array_size) + ')'
        ),
        args = args
    )


def gen_init_string(type, initializer, indent):
    init_code = ""
    if initializer is not None:
        raw_code = type.gen_usage_string(initializer)
        # add indent to initializer code
        init_code_lines = raw_code.split('\n')
        init_code = "@b=@b" + init_code_lines[0]
        for line in init_code_lines[1:]:
            init_code += "\n" + indent + line
    return init_code


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
        # Note that 0-th chunk is the global and rest are its dependencies
        references.append(generator.provide_chunks(t)[0])

    return references


class FunctionDeclaration(SourceChunk):
    weight = 6

    def __init__(self, function, indent = ""):
        super(FunctionDeclaration, self).__init__(function,
            "Declaration of function %s" % function,
            "%s;" % gen_function_declaration_string(indent, function)
        )


class FunctionDefinition(SourceChunk):

    def __init__(self, function, indent = "", append_nl = True):
        body = " {}" if function.body is None else "\n{\n%s}" % function.body

        if append_nl:
            body += "\n"

        super(FunctionDefinition, self).__init__(function,
            "Definition of function %s" % function,
            "{dec}{body}\n".format(
                dec = gen_function_declaration_string(indent, function),
                body = body
            )
        )


def depth_first_sort(chunk, new_chunks):
    # visited:
    # 0 - not visited
    # 1 - visited
    # 2 - added to new_chunks
    chunk.visited = 1
    for ch in sorted(chunk.references):
        if ch.visited == 2:
            continue
        if ch.visited == 1:
            msg = "A loop is found in source chunk references on chunk: %s" % (
                chunk.name
            )
            if isinstance(ch, HeaderInclusion):
                # XXX: Allow loop of header inclusions and hope that they
                # will eat each other during inclusion optimization pass.
                print(msg)
                continue
            else:
                raise RuntimeError(msg)
        depth_first_sort(ch, new_chunks)

    chunk.visited = 2
    new_chunks.add(chunk)


class SourceFile(object):

    def __init__(self, origin, protection = True):
        self.name = splitext(basename(origin.path))[0]
        self.is_header = type(origin) is Header
        # Note that, chunk order is significant while one reference per chunk
        # is enough.
        self.chunks = OrderedSet()
        self.sort_needed = False
        self.protection = protection
        self.origin = origin

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

        upper_cnn = None
        for ch in self.chunks:
            cnn = chunk_node_name(ch)
            label = ch.name

            if isinstance(ch, HeaderInclusion):
                label += "\\n*\\n"
                for r in ch.reasons:
                    label += "%s %s\\l" % r

            label = label.replace('"', '\\"')

            w.write('\n    %s [label="%s"]\n' % (cnn, label))

            # invisible edges provides vertical order like in the output file
            if upper_cnn is not None:
                w.write("\n    %s -> %s [style=invis]\n" % (cnn, upper_cnn))
            upper_cnn = cnn

            if ch.references:
                w.write("        /* References */\n")
                for ref in sorted(ch.references):
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

        for _, _type in ch_remove.reasons:
            ch.add_reason(_type, kind = "provides")

        self.chunks.remove(ch_remove)

    def remove_chunks_with_same_origin(self, types = None, check_only = True):
        if types is not None:
            types = set(types)

        all_exists = defaultdict(dict)
        sort_needed = False

        for ch in list(self.chunks):
            t = type(ch)

            # exact type match is required
            if not (types is None or t in types):
                continue

            exists = all_exists[t]

            origin = ch.origin

            if origin in exists:
                ech = exists[origin]
                if check_only:
                    raise AssertionError("Chunks %s and %s are both"
                        " originated from %s" % (ch.name, ech.name, origin)
                    )

                self.remove_dup_chunk(ech, ch)

                sort_needed = True
            else:
                exists[origin] = ch

        if sort_needed:
            self.sort_needed = True

    def sort_chunks(self):
        if not self.sort_needed:
            return

        new_chunks = OrderedSet()
        # topology sorting
        for chunk in self.chunks:
            if not chunk.visited == 2:
                depth_first_sort(chunk, new_chunks)

        for chunk in new_chunks:
            chunk.visited = 0

        self.chunks = new_chunks

    def add_chunks(self, chunks):
        for ch in chunks:
            self.add_chunk(ch)

    def add_chunk(self, chunk):
        if chunk.source is None:
            self.sort_needed = True
            self.chunks.add(chunk)

            # Also add referenced chunks into the source
            for ref in chunk.references:
                self.add_chunk(ref)
        elif not chunk.source == self:
            raise RuntimeError("The chunk %s is already in %s"
                % (chunk.name, chunk.source.name)
            )

    def optimize_inclusions(self, log = lambda *args, **kw : None):
        log("-= inclusion optimization started for %s.%s =-" % (
            (self.name, "h" if self.is_header else "c")
        ))

        for h in Header.reg.values():
            h.root = None

        # Dictionary is used for fast lookup HeaderInclusion by Header.
        # Assuming only one inclusion per header.
        included_headers = {}

        for ch in self.chunks:
            if isinstance(ch, HeaderInclusion):
                h = ch.origin
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

        # Sorting criteria:
        # 1) Headers with a larger number of users are preferable to use for
        #    substitution since the number of references will probably decrease
        #    faster.
        # 2) Headers with a same number of users ordered by its chunks.
        stack = list(sorted(included_headers,
            key = lambda header: (
                -len(included_headers[header].users),
                included_headers[header]
            ),
            reverse = True
        ))

        while stack:
            h = stack.pop()

            for sp in h.inclusions:
                s = Header[sp]
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

                    if redundant.origin is not s:
                        # inclusion of s was already removed as redundant
                        log("%s includes %s which already substituted by "
                            "%s" % (h.root.path, s.path, redundant.origin.path)
                        )
                        continue

                    log("%s includes %s, substitute %s with %s" % (
                        h.root.path, s.path, redundant.origin.path,
                        substitution.origin.path
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
            del h.root

        log("-= inclusion optimization ended =-")

    def check_static_function_declarations(self):
        func_dec = {}
        for ch in list(self.chunks):
            if not isinstance(ch, (FunctionDeclaration, FunctionDefinition)):
                continue

            f = ch.origin

            if not f.static:
                continue

            try:
                prev_ch = func_dec[f]
            except KeyError:
                func_dec[f] = ch
                continue

            # TODO: check for loops in references, the cases in which forward
            # declarations is really needed.

            if isinstance(ch, FunctionDeclaration):
                self.remove_dup_chunk(prev_ch, ch)
            elif type(ch) is type(prev_ch):
                # prev_ch and ch are FunctionDefinition
                self.remove_dup_chunk(prev_ch, ch)
            else:
                # prev_ch is FunctionDeclaration but ch is FunctionDefinition
                self.remove_dup_chunk(ch, prev_ch)
                func_dec[f] = ch

    def header_paths_shortening(self):
        origin_dir = dirname(self.origin.path)

        for ch in self.chunks:
            if not isinstance(ch, HeaderInclusion):
                continue

            header_path = ch.origin.path
            if origin_dir == dirname(header_path):
                path = (basename(header_path),)
            else:
                path = path2tuple(header_path)
                # TODO: those are domain specific values, make them global
                # parameters
                if path[0] in ("include", "tcg"):
                    path = path[1:]
            ch.path = path

    def generate(self, writer,
        gen_debug_comments = False,
        append_nl_after_headers = True
    ):
        # check for duplicate chunks for same origin
        self.remove_chunks_with_same_origin()

        self.check_static_function_declarations()

        self.sort_chunks()

        if OPTIMIZE_INCLUSIONS:
            self.optimize_inclusions()

        self.header_paths_shortening()

        # semantic sort
        self.chunks = OrderedSet(sorted(self.chunks))

        self.sort_chunks()

        writer.write(
            "/* %s.%s */\n" % (self.name, "h" if self.is_header else "c")
        )

        if self.is_header and self.protection:
            writer.write("""\
#ifndef INCLUDE_{name}_H
#define INCLUDE_{name}_H
""".format(name = self.name_for_macro())
            )

        prev_header = False
        prev_macro = False

        for chunk in self.chunks:
            # Add empty lines after some chunk groups for prettiness.
            if isinstance(chunk, HeaderInclusion):
                # propagate actual inclusions back to the origin
                if self.is_header:
                    self.origin.add_inclusion(chunk.origin)

                prev_header = True
            else:
                if append_nl_after_headers and prev_header:
                    writer.write("\n")
                prev_header = False

                if isinstance(chunk, MacroDefinition):
                    prev_macro = True
                else:
                    if APPEND_NL_AFTER_MACROS and prev_macro:
                        writer.write("\n")
                    prev_macro = False

            chunk.check_cols_fix_up()

            if gen_debug_comments:
                writer.write("/* source chunk %s */\n" % chunk.name)
            writer.write(chunk.code)

        if self.is_header and self.protection:
            writer.write(
                "#endif /* INCLUDE_%s_H */\n" % self.name_for_macro()
            )

    def name_for_macro(self):
        return macro_forbidden.sub('_', self.name.upper())

# Source tree container


HDB_HEADER_PATH = "path"
HDB_HEADER_IS_GLOBAL = "is_global"
HDB_HEADER_INCLUSIONS = "inclusions"
HDB_HEADER_MACROS = "macros"


class SourceTreeContainer(object):
    current = None

    def __init__(self):
        self.reg_header = {}
        self.reg_type = {}

        # add preprocessor macros those are always defined
        prev = self.set_cur_stc()

        CPPMacro("__FILE__")
        CPPMacro("__LINE__")
        CPPMacro("__FUNCTION__")

        if prev is not None:
            prev.set_cur_stc()

    def type_lookup(self, name):
        if name not in self.reg_type:
            raise TypeNotRegistered("Type with name %s is not registered"
                % name
            )
        return self.reg_type[name]

    def type_exists(self, name):
        try:
            self.type_lookup(name)
            return True
        except TypeNotRegistered:
            return False

    def header_lookup(self, path):
        tpath = path2tuple(path)

        if tpath not in self.reg_header:
            raise RuntimeError("Header with path %s is not registered" % path)
        return self.reg_header[tpath]

    def gen_header_inclusion_dot_file(self, dot_file_name):
        dot_writer = open(dot_file_name, "w")

        dot_writer.write("""\
digraph HeaderInclusion {
    node [shape=polygon fontname=Monospace]
    edge[style=filled]

"""
        )

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

                dot_writer.write("    %s -> %s\n" % (i_node, h_node))

        dot_writer.write("}\n")

        dot_writer.close()

    def co_load_header_db(self, list_headers):
        # Create all headers
        for dict_h in list_headers:
            path = dict_h[HDB_HEADER_PATH]
            if path2tuple(path) not in self.reg_header:
                Header(
                    path = dict_h[HDB_HEADER_PATH],
                    is_global = dict_h[HDB_HEADER_IS_GLOBAL]
                )
            else:
                # Check if existing header equals the one from database?
                pass

        # Set up inclusions
        for dict_h in list_headers:
            yield

            path = dict_h[HDB_HEADER_PATH]
            h = self.header_lookup(path)

            for inc in dict_h[HDB_HEADER_INCLUSIONS]:
                i = self.header_lookup(inc)
                h.add_inclusion(i)

            for m in dict_h[HDB_HEADER_MACROS]:
                h.add_type(Macro.new_from_dict(m))

    def create_header_db(self):
        list_headers = []
        for h in self.reg_header.values():
            dict_h = {}
            dict_h[HDB_HEADER_PATH] = h.path
            dict_h[HDB_HEADER_IS_GLOBAL] = h.is_global

            inc_list = []
            for i in h.inclusions.values():
                inc_list.append(i.path)
            dict_h[HDB_HEADER_INCLUSIONS] = inc_list

            macro_list = []
            for t in h.types.values():
                if isinstance(t, Macro):
                    macro_list.append(t.gen_dict())
            dict_h[HDB_HEADER_MACROS] = macro_list

            list_headers.append(dict_h)

        return list_headers

    def set_cur_stc(self):
        Header.reg = self.reg_header
        Type.reg = self.reg_type

        previous = SourceTreeContainer.current
        SourceTreeContainer.current = self
        return previous


SourceTreeContainer().set_cur_stc()
