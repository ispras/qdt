__all__ = [
    "Source"
      , "Header"
  , "AddTypeRefToDefinerException"
  , "TypeNotRegistered"
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
  , "Initializer"
  , "Variable"
  , "SourceChunk"
      , "HeaderInclusion"
      , "MacroDefinition"
      , "PointerTypeDeclaration"
      , "FunctionPointerTypeDeclaration"
      , "MacroTypeChunk"
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
      , "EnumerationDeclarationBegin"
      , "EnumerationDeclarationEnd"
      , "EnumerationElementDeclaration"
      , "OpaqueChunk"
  , "SourceFile"
  , "SourceTreeContainer"
  , "TypeReferencesVisitor"
  , "NodeVisitor"
  , "ANC"
  , "CAN"
  , "NBS"
  , "NSS"
  , "disable_auto_lock_sources"
  , "enable_auto_lock_sources"
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
    count,
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


APPEND_NL_AFTER_HEADERS = not ee("QDT_NO_NL_AFTER_HEADERS")

APPEND_NL_AFTER_MACROS = not ee("QDT_NO_NL_AFTER_MACROS")

# All sources which are not created at the code generation stage considered
# immutable. We believe that these files already exist. Therefore, we cannot
# influence the list of their inclusions. To prevent the appearance of new
# inclusions, the flag `locked` is set. Few exceptions:
# - explicit `locked` setting
# - `add_inclusion` method will add inclusion even to a locked file
AUTO_LOCK_SOURCES = True


# Code generation model
class ChunkGenerator(object):
    """ Maintains context of source code chunks generation process. """

    def __init__(self, definer):
        self.chunk_cache = { definer: [], CPP: [] }
        self.for_header = isinstance(definer, Header)
        self.references = definer.references
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
            elif (    isinstance(origin, TypeReference)
                  and origin.type in self.references
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

    def __init__(self, path, locked = None):
        self.path = path
        self.types = {}
        self.inclusions = {}
        self.global_variables = {}
        self.references = set()
        self.protection = False
        if locked is not None:
            self.locked = locked
        else:
            self.locked = AUTO_LOCK_SOURCES

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

        TypeFixerVisitor(self, var).visit()

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

                        # A `t`ype can be locally defined within something
                        # (e.g. `Type`). There we looks for source-level
                        # container of the `t`ype.
                        while not isinstance(s, Source):
                            s = s.definer

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
                    if not t.is_named:
                        continue
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
        if _type.is_named:
            self.types[_type.name] = _type
        else:
            # Register the type with any name in order to be able to generate
            # its chunks.
            self.types[".anonymous" + str(id(_type))] = _type

        # Some types (like `Enumeration`) contains types without definer or
        # may reference to other just created types.
        # They must be added right now (by `TypeFixerVisitor`) to prevent
        # capturing by other sources at generation begin.
        # Note, replacement of foreign types with `TypeReference` is actually
        # not required right now (see `gen_chunks`).

        TypeFixerVisitor(self, _type).visit()

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

        # This header includes other headers to provide types for includers
        # of self. This is list of references to those types.
        ref_list = []

        if isinstance(self, Header):
            for user in self.includers:
                for ref in user.references:
                    if ref.definer not in user.inclusions:
                        ref_list.append(TypeReference(ref))

        # Finally, we must fix types just before generation because user can
        # change already added types.
        TypeFixerVisitor(self, self).visit()

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
                        # Definer of a foreign type (t is TypeReference to it)
                        # may depend on an inner type (ref) from the current
                        # file (self). In this case, inclusion of that definer
                        # must be placed below the inner type in resulting
                        # file. Adding ref to definer_references results in the
                        # required order among code chunks.
                        if ref.definer is self:
                            # Here ref is Type (not TypeReference) because
                            # defined in the current file.
                            t.definer_references.add(ref)
                        else:
                            # Definer of a foreign type (t) may depend on a
                            # foreign type (ref) from another file, which will
                            # be included in the resulting file (since we use
                            # some type from it). In this case, inclusion of
                            # that definer must be placed below the inclusion
                            # of another file in the resulting file.
                            for tt in l:
                                if not isinstance(tt, TypeReference):
                                    continue
                                if ref.definer is tt.type.definer:
                                    t.definer_references.add(ref)
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

    __type_references__ = ("types", "global_variables")


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

    def __init__(self, path,
        is_global = False,
        protection = True,
        locked = None
    ):
        """
:param path: it is used in #include statements, as unique identifier and
    somehow during code generation.
:param is_global: inclusions will use <path> instead of "path".
:param protection: wrap content in multiple inclusion protection macro logic.
        """
        super(Header, self).__init__(path, locked)
        self.is_global = is_global
        self.includers = []
        self.protection = protection

        tpath = path2tuple(path)
        if tpath in Header.reg:
            raise RuntimeError("Header %s is already registered" % path)

        Header.reg[tpath] = self

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
                args = (
                    None if macro.arglist is None else list(macro.arglist)
                ),
                text = "".join(tok.value for tok in macro.value)
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
                    p.all_inclusions = True
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
    def co_build_inclusions(work_dir, include_paths):
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

        for path, recursive in include_paths:
            dname = join(work_dir, path)
            for entry in listdir(dname):
                yield Header._build_inclusions(dname, entry, recursive)

        for h in Header.reg.values():
            del h.parsed

        sys.stdout = sys_stdout_recovery

        yields_total = sum(Header.yields_per_header)

        if yields_total:
            print("""Header inclusions build statistic:
    Yields total: %d
    Max yields per header: %d
    Min yields per header: %d
    Average yields per header: %f
""" % (
    yields_total,
    max(Header.yields_per_header),
    min(Header.yields_per_header),
    yields_total / float(len(Header.yields_per_header))
)
            )
        else:
            print("Headers not found")

        del Header.yields_per_header

    @staticmethod
    def lookup(path):
        tpath = path2tuple(path)

        if tpath not in Header.reg:
            raise RuntimeError("Header with path %s is not registered" % path)
        return Header.reg[tpath]

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
        if _type.is_named:
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

    def gen_chunks(self, generator):
        fields_indent = "    "
        indent = ""

        if self._definition is not None:
            return [StructureForwardDeclaration(self, indent)]

        if self.declaration is None:
            struct_begin = StructureTypedefDeclarationBegin(self, indent)
            struct_end = StructureTypedefDeclarationEnd(self, indent, True)
        else:
            struct_begin = StructureDeclarationBegin(self, indent)
            struct_end = StructureDeclarationEnd(self, indent, True)

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
            field_decl = generator.provide_chunks(f, indent = field_indent)[0]
            field_refs.extend(list(field_decl.references))
            field_decl.clean_references()
            field_decl.add_reference(top_chunk)
            top_chunk = field_decl

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
            # It's a definition. A forward declaration cannot have fields.
            # Hence, all fields are in _and only in_ `self._fields`.
            # And the `property`s logic is not required for this case.
            return ["_fields"]
        else:
            return []

    def __c__(self, writer):
        writer.write(self.c_name)


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
        for key, val in elems_list:
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

    def gen_chunks(self, generator):
        ch = OpaqueChunk(self)

        for item in self.used:
            ch.add_references(generator.provide_chunks(item))

        return [ch]

    __type_references__ = ["used"]


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

    def gen_declaration_chunks(self, generator,
        indent = "",
        extern = False
    ):
        type_ = self.type
        if (    isinstance(type_, Pointer)
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

            # Skip pointer and macrousage types without name. Nameless
            # pointer or macrousage does not have definer and should not be
            # replaced with type reference.
            if isinstance(t, (Pointer, MacroUsage)) and not t.is_named:
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

            # A type defined inside another type is not subject of this fixer.
            # Because internal type is always defined within its container and,
            # hence, never defined by a header inclusion or directly by a
            # source.
            # Note that `definer` is not visited by this type fixer. Hence,
            # the field is never a `TypeReference`.
            # Note that if we are here then topmost container of the `t`ype is
            # within `self.source`.
            # Else, the topmost container is replaced with a `TypeReference`
            # and a `BreakVisiting` is raised (see above).
            if isinstance(t.definer, Type):
                return

            # replace foreign type with reference to it
            try:
                tr = self.source.types[t.name]
            except KeyError:
                tr = TypeReference(t)
                self.source.types[t.name] = tr
                self.new_type_references.append(tr)

            self.replace(tr)

    def visit(self):
        ret = super(TypeFixerVisitor, self).visit()

        # Auto add references to types this type_object does depend on
        s = self.source
        # The current approach does not generate header inclusion chunks for
        # foreign types which are contained in the `references` list.
        if s.locked:
            s.add_references(tr.type for tr in self.new_type_references)
        elif SKIP_GLOBAL_HEADERS and isinstance(s, Header):
            for tr in self.new_type_references:
                t = tr.type
                definer = t.definer
                # A type declared in a global header is added to the
                # `references` list to prevent the inclusion of the global
                # header.
                if isinstance(definer, Header) and definer.is_global:
                    s.references.add(t)
        return ret

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

# Source code instances


class SourceChunk(object):
    """
`weight` is used during coarse chunk sorting. Chunks with less `weight` value
    are moved to the top of the file. Then all chunks are ordered topologically
    (with respect to inter-chunk references). But chunks which is not linked
    by references will preserve `weight`-based order.

`group` is used during chunk printing. Chunks from different groups will be
    separated by an empty line for prettiness. `group` is an unique reference.
    """
    weight = 5
    group = object()

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
        sw = self.weight
        ow = other.weight
        if sw < ow:
            return True
        elif sw > ow:
            return False
        else:
            return self.name < other.name


class HeaderInclusion(SourceChunk):
    weight = 0

    if APPEND_NL_AFTER_HEADERS:
        group = object()

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

    if APPEND_NL_AFTER_MACROS:
        group = object()

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
            "typedef@b" + _type.declaration_string + '*' + def_name + ";\n"
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


class MacroTypeChunk(SourceChunk):

    def __init__(self, _type, indent = ""):
        super(MacroTypeChunk, self).__init__(_type,
            "Usage of type %s" % _type,
            code = indent + _type.macro.gen_usage_string(_type.initializer)
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
{indent}{extern}{var_declaration};
""".format(
    indent = indent,
    extern = "extern@b" if extern else "",
    var_declaration = var.declaration_string
            )
        )


class VariableDefinition(SourceChunk):
    weight = 5

    def __init__(self, var, indent = "", append_nl = True, separ = ";"):
        super(VariableDefinition, self).__init__(var,
            "Variable %s of type %s definition" % (var, var.type),
            """\
{indent}{var_declaration}{used}{init}{separ}{nl}
""".format(
    indent = indent,
    var_declaration = var.declaration_string,
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

    def __init__(self, struct, indent = ""):
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

    def __init__(self, struct, indent = "", append_nl = True):
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

    def __init__(self, struct, indent = ""):
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

    def __init__(self, struct, indent = "", append_nl = True):
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
            "Beginning of enumeration %s declaration" % enum,
            """\
{indent}{typedef}enum@b{enum_name}{{
""".format(
    indent = indent,
    typedef = "typedef@b" if enum.typedef else "",
    enum_name = (enum.enum_name + "@b") if enum.enum_name is not None else ""
            )
        )


class EnumerationDeclarationEnd(SourceChunk):
    weight = 3

    def __init__(self, enum, indent = ""):
        super(EnumerationDeclarationEnd, self).__init__(enum,
            "Ending of enumeration %s declaration" % enum,
            """\
{indent}}}{typedef_name};\n
""".format(
    indent = indent,
    typedef_name = ("@b" + enum.typedef_name) if enum.typedef else ""
            )
        )


class EnumerationElementDeclaration(SourceChunk):

    def __init__(self, elem, indent = "", separ = ","):
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
        args = ",@s".join(a.declaration_string for a in function.args)

    return "{indent}{static}{inline}{ret_type}{name}(@a{args}@c)".format(
        indent = indent,
        static = "static@b" if function.static else "",
        inline = "inline@b" if function.inline else "",
        ret_type = function.ret_type.declaration_string,
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
        references.extend(generator.provide_chunks(t))

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


class OpaqueChunk(SourceChunk):

    def __init__(self, origin):
        name = "Opaque code named %s" % origin

        super(OpaqueChunk, self).__init__(origin, name, str(origin.code))

        # Ordering weight can be overwritten.
        if origin.weight is not None:
            self.weight = origin.weight


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


def sort_chunks(chunks):
    new_chunks = OrderedSet()
    # topology sorting
    for chunk in chunks:
        if not chunk.visited == 2:
            depth_first_sort(chunk, new_chunks)

    for chunk in new_chunks:
        chunk.visited = 0

    return new_chunks


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

    def gen_chunks_graph(self, w, chunks):
        w.write("""\
digraph Chunks {
    rankdir=BT;
    node [shape=polygon fontname=Momospace]
    edge [style=filled]

"""
        )

        if self.origin.references:
            def ref_node_name(ref, mapping = {}, counter = count(0)):
                try:
                    name = mapping[ref]
                except KeyError:
                    name = "ref_%u" % next(counter)
                    mapping[ref] = name
                return name

            w.write("    /* Source references */\n")
            for ref in self.origin.references:
                w.write('    %s [style=dashed label="%s"]\n\n' % (
                    ref_node_name(ref), ref
                ))

        w.write("    /* Chunks */\n")

        def chunk_node_name(chunk, mapping = {}, counter = count(0)):
            try:
                name = mapping[chunk]
            except KeyError:
                name = "ch_%u" % next(counter)
                mapping[chunk] = name
            return name

        upper_cnn = None
        for ch in chunks:
            cnn = chunk_node_name(ch)
            label = ch.name

            if isinstance(ch, HeaderInclusion):
                style = "style=filled "
                label += "\\n*\\n"
                for r in ch.reasons:
                    label += "%s %s\\l" % r
            else:
                style = ''

            label = label.replace('"', '\\"')

            w.write('\n    %s [%slabel="%s"]\n' % (cnn, style, label))

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
        chunks = sort_chunks(OrderedSet(sorted(self.chunks)))

        f = open(file_name, "w")
        self.gen_chunks_graph(f, chunks)
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
        gen_debug_comments = False
    ):
        # check for duplicate chunks for same origin
        self.remove_chunks_with_same_origin()

        self.check_static_function_declarations()

        if self.sort_needed:
            self.chunks = sort_chunks(self.chunks)

        if OPTIMIZE_INCLUSIONS:
            self.optimize_inclusions()

        self.header_paths_shortening()

        # semantic sort
        self.chunks = OrderedSet(sorted(self.chunks))

        if self.sort_needed:
            self.chunks = sort_chunks(self.chunks)

        writer.write(
            "/* %s.%s */\n" % (self.name, "h" if self.is_header else "c")
        )

        if self.is_header and self.protection:
            writer.write("""\
#ifndef INCLUDE_{name}_H
#define INCLUDE_{name}_H
""".format(name = self.name_for_macro())
            )

        prev_group = None

        for chunk in self.chunks:
            # propagate actual inclusions back to the origin
            if isinstance(chunk, HeaderInclusion) and self.is_header:
                self.origin.add_inclusion(chunk.origin)

            # Add empty line between chunks of different groups.
            # This also adds empty line before first chunk because initially
            # prev_group is None.
            if prev_group is not chunk.group:
                writer.write("\n")
            prev_group = chunk.group

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


def disable_auto_lock_sources():
    global AUTO_LOCK_SOURCES
    AUTO_LOCK_SOURCES = False


def enable_auto_lock_sources():
    global AUTO_LOCK_SOURCES
    AUTO_LOCK_SOURCES = True


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
        CPPMacro("__func__")

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
