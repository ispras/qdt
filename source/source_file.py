__all__ = [
    "disable_auto_lock_inclusions"
  , "enable_auto_lock_inclusions"
  , "Source"
      , "Header"
  , "SourceFile"
  , "SourceTreeContainer"
]

from collections import (
    deque,
    defaultdict,
)
from itertools import (
    count,
)
from os import (
    listdir,
)
from os.path import (
    basename,
    dirname,
    isdir,
    join,
    splitext,
)
from re import (
    compile,
)
import sys
from six import (
    add_metaclass,
)
from common import (
    SkipVisiting,
    ee,
    OrderedSet,
    path2tuple,
    pypath,
)
from .chunks import (
    FunctionDeclaration,
    FunctionDefinition,
    HeaderInclusion,
)
from .function import (
    BodyTree,
    VarDeclarator,
)
from .model import (
    CPP,
    CPPMacro,
    Function,
    Macro,
    registry,
    Structure,
    Type,
    TypeNotRegistered,
    TypeReferencesVisitor,
    Variable,
)
from .tools import (
    get_cpp_search_paths,
)
from .type_container import (
    TypeContainer,
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

# All sources which are not created at the code generation stage considered
# immutable. We believe that these files already exist. Therefore, we cannot
# influence the list of their inclusions. To prevent the appearance of new
# inclusions, the flag `locked_inclusions` is set. Few exceptions:
# - explicit `locked_inclusions` setting
# - `add_inclusion` method will add inclusion even to a file with locked
# inclusions
AUTO_LOCK_INCLUSIONS = True

def disable_auto_lock_inclusions():
    global AUTO_LOCK_INCLUSIONS
    AUTO_LOCK_INCLUSIONS = False


def enable_auto_lock_inclusions():
    global AUTO_LOCK_INCLUSIONS
    AUTO_LOCK_INCLUSIONS = True


# Reduces amount of #include directives
OPTIMIZE_INCLUSIONS = ee("QDT_OPTIMIZE_INCLUSIONS", "True")
# Skip global headers inclusions. All needed global headers included in
# "qemu/osdep.h".
NO_GLOBAL_HEADERS = ee("QDT_NO_GLOBAL_HEADERS", "True")


class Source(TypeContainer):

    # Only header can do it, see `Header`.
    inherit_references = False

    def __init__(self, path,
        locked_inclusions = None,
        **kw
    ):
        super(Source, self).__init__(**kw)

        self.path = path
        self.types = {}
        self.inclusions = {}
        self.global_variables = {}
        self.references = set()
        self.protection_prefix = None
        if locked_inclusions is not None:
            self.locked_inclusions = locked_inclusions
        else:
            self.locked_inclusions = AUTO_LOCK_INCLUSIONS

    def add_reference(self, ref):
        if not isinstance(ref, (Type, Variable)):
            raise ValueError("Trying to add source reference which is not a"
                " type"
            )
        self.references.add(ref)

        return self

    def add_references(self, refs):
        for ref in refs:
            self.add_reference(ref)

        return self

    def add_global_variable(self, var,
        grab_used_vars = False
    ):
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
            initializer = var.initializer
            if initializer is not None:
                for t in initializer.used_types:
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
                if grab_used_vars:
                    for used_var in initializer.used_variables:
                        if used_var.definer is None:
                            self.add_global_variable(used_var,
                                grab_used_vars = True,
                            )

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
                if t.is_named:
                    self._add_type_recursive(t)

            if self in header.includers:
                raise RuntimeError("Header %s is among includers of %s but"
                    " does not includes it" % (self.path, header.path)
                )

            header.includers.append(self)

        return self

    def _add_type_recursive(self, type_):
        # adding a type may satisfy a dependency
        if type_ in self.references:
            self.references.remove(type_)

        if type_.name in self.types:
            t = self.types[type_.name]
            if t is not type_:
                raise RuntimeError("Type conflict (%s) found in"
                    " source %s. The type is defined both in %s and %s"
                    % (t, self.path, type_.definer.path, t.definer.path)
                )
            # To make more conflicts checking
            return False

        self.types[type_.name] = type_
        return True

    def add_types(self, types):
        for t in types:
            self.add_type(t)

        return self

    def __call__(self, *types):
        return self.add_types(types)

    def add_type(self, _type):
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

        TypeFixerVisitor(self, _type).visit()

        # Addition of a required type does satisfy the dependence.
        if _type in self.references:
            self.references.remove(_type)

        return self

    def gen_chunks(self):
        inherit_references = self.inherit_references
        if inherit_references:
            assert(isinstance(self, Header))

        # Auto `Declare` variables in `Function`s with `BodyTree`.
        for func in self.types.values():
            if not isinstance(func, Function):
                continue
            if func.definer is not self:
                continue
            body = func.body
            if not isinstance(body, BodyTree):
                continue
            VarDeclarator(body, func.args).visit()

        # This header includes other headers to provide types for includers
        # of self. This is list of references to those types.
        ref_list = []

        if isinstance(self, Header) and not self.locked_inclusions:
            for user in self.includers:
                for ref in user.references:
                    if ref.definer not in user.inclusions:
                        ref_list.append(ref)

        # Finally, we must fix types just before generation because user can
        # change already added types.
        TypeFixerVisitor(self, self).visit()

        gen = ChunkGenerator(self)

        for t in self.types.values():
            if t.definer is self:
                gen.provide_chunks(t)

        for gv in self.global_variables.values():
            gen.provide_chunks(gv)

        if isinstance(self, Header):
            for r in ref_list:
                gen.provide_chunks(r)

        chunks = gen.get_all_chunks()

        return chunks

    def generate(self):
        Header.propagate_references()

        file = SourceFile(self, protection_prefix = self.protection_prefix)

        file.add_chunks(self.gen_chunks())

        return file

    __type_references__ = ("types", "global_variables")

    def __repr__(self):
        return type(self).__name__ + "(%r)" % self.path

    def __getitem__(self, name):
        "Shortcut for types and global variables"
        try:
            return self.types[name]
        except KeyError:
            try:
                return self.global_variables[name]
            except KeyError:
                pass
        raise ValueError("Undefined name " + name)


class TypeFixerVisitor(TypeReferencesVisitor):

    def __init__(self, source, type_object):
        super(TypeFixerVisitor, self).__init__(type_object)

        self.source = source
        self.required_types = deque()

    def on_visit(self):
        if isinstance(self.cur, Type):
            t = self.cur

            if t.base:
                raise SkipVisiting()

            if not t.is_named:
                return

            if t.definer is self.source:
                return

            # Add definerless types to the Source automatically
            if t.definer is None:
                self.source.add_type(t)
                return

            # A type defined inside another type is not subject of this fixer.
            # Because internal type is always defined within its container and,
            # hence, never defined by a header inclusion or directly by a
            # source.
            if isinstance(t.definer, Type):
                return

            # if the `t`ype is not provided by an inclusion, it should be
            # either referenced or provided by corresponding inclusion.
            if t.name not in self.source.types:
                self.required_types.append(t)

            # Do not enter another source (`t`ype's definer).
            raise SkipVisiting()

    def visit(self):
        ret = super(TypeFixerVisitor, self).visit()

        s = self.source
        if s.locked_inclusions:
            # A generated file either provides required types by inclusions or
            # adds them to its references.
            # A constant (`locked_inclusions`) file can only update its
            # references.
            s.add_references(self.required_types)
        else:
            for t in self.required_types:
                definer = t.definer

                # Sometimes headers do not include other headers to provide
                # visibility of used types. A module file must provide it.
                if (    isinstance(s, Header)
                    and s.no_global_headers
                    and isinstance(definer, Header)
                    and definer.is_global
                ):
                    # A type declared in a global header is added to the
                    # `references` list to prevent the inclusion of that
                    # global header.
                    # Note, the current approach does not generate header
                    # inclusion chunks for foreign types which are contained
                    # in the `references` list.
                    s.add_reference(t)
                else:
                    # The `t`ype will be provided by an inclusion after the
                    # file generation.
                    s._add_type_recursive(t)

        return ret


# A Py version independent way to add metaclass.
# https://stackoverflow.com/questions/39013249/metaclass-in-python3-5
@add_metaclass(registry)
class Header(Source):
    reg = {}

    # In some use cases header should not satisfy references of its
    # inclusions by itself. Instead, it must inherit them. A source file must
    # satisfy the references in such case. Set inherit_references to True for
    # switching to that mode.
    # TODO: current value of inherit_references is dictated by Qemu
    # coding policy. Hence, version API must be used there.
    inherit_references = True

    def __init__(self, path,
        is_global = False,
        protection_prefix = "INCLUDE_",
        locked_inclusions = None,
        no_global_headers = NO_GLOBAL_HEADERS
    ):
        """
:param path: it is used in #include statements, as unique identifier and
    somehow during code generation.
:param is_global: inclusions will use <path> instead of "path".
:param protection_prefix: wrap content in multiple inclusion protection macro
    logic. The protection macro is prefixed with `protection_prefix`.
    `None` `protection_prefix` disables protection.
    "" `protection_prefix` results in only header name in protection macro.
        """
        super(Header, self).__init__(path, locked_inclusions)
        self.is_global = is_global
        self.includers = []
        self.protection_prefix = protection_prefix
        self.no_global_headers = no_global_headers

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
    def co_build_inclusions(work_dir, include_paths,
        # the reference is saved at class creation time
        _sys_stdout_recovery = sys.stdout
    ):
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

        sys.stdout = _sys_stdout_recovery

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
        # Always use UNIX path separator
        path = "/".join(path2tuple(self.path))
        if self.is_global:
            return "<%s>" % path
        else:
            return '"%s"' % path

    def _add_type_recursive(self, type_):
        # Preventing infinite recursion by header inclusion loop
        if super(Header, self)._add_type_recursive(type_):
            # Type was added. Hence, It is new type for the header
            for s in self.includers:
                s._add_type_recursive(type_)

    def add_type(self, _type):
        super(Header, self).add_type(_type)

        # Auto add type references to self includers
        if _type.is_named:
            for s in self.includers:
                s._add_type_recursive(_type)

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


class ParsePrintFilter(object):

    def __init__(self, out):
        self.out = out
        self.written = False

    def write(self, _str):
        if _str.startswith("Info:"):
            self.out.write(_str + "\n")
            self.written = True

    def flush(self):
        if self.written:
            self.out.flush()
            self.written = False


# Code generation model
class ChunkGenerator(object):
    """ Maintains context of source code chunks generation process. """

    def __init__(self, definer):
        self.definer = definer
        self.chunk_cache = { definer: [], CPP: [] }
        self.for_header = isinstance(definer, Header)
        """ Tracking of recursive calls of `provide_chunks`. Currently used
        only to generate "extern" keyword for global variables in header and to
        distinguish structure fields and normal variables. """
        self.stack = []

    def provide_chunks(self, origin, **kw):
        """ Given origin the method returns chunk list generating it on first
        access. """
        current = self.definer
        if (    origin.definer is not current
            # Note, it can be a type inside another type.
            and isinstance(origin.definer, Source)
        ):
            key = origin.definer
            foreign = True
        else:
            key = origin
            foreign = False

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

            if isinstance(origin, Type) and foreign:
                chunks = self._gen_foreign_type_chunks(origin)
            elif isinstance(origin, Function):
                if (    self.for_header
                    and (not origin.static or not origin.inline)
                ):
                    chunks = origin.gen_declaration_chunks(self, **kw)
                else:
                    chunks = origin.gen_definition_chunks(self, **kw)
            elif isinstance(origin, Variable):
                if origin.definer is not None or origin.declarer is not None:
                    # It is a global variable
                    if self.for_header:
                        foreign = origin.declarer is not current
                    else:
                        foreign = origin.definer is not current

                    if foreign:
                        declarer = origin.declarer
                        if declarer is None:
                            raise RuntimeError("Variable '%s' is only defined"
                                " in '%s' but not declared in any header" % (
                                    origin, origin.definer.path
                                )
                            )
                        try:
                            chunks = self.chunk_cache[declarer]
                        except KeyError:
                            chunks = [
                                HeaderInclusion(declarer).add_reason(origin,
                                    kind = "declares"
                                )
                            ]
                    else:
                        # A variable in a header does always have `extern`
                        # modifier.
                        if self.for_header:
                            kw["extern"] = True
                            chunks = origin.gen_declaration_chunks(self, **kw)
                        else:
                            chunks = origin.get_definition_chunks(self, **kw)
                else:
                    # It is a variable inside something
                    if (    len(self.stack) > 1
                        and isinstance(self.stack[-2], (Structure, Variable))
                    ):
                        # structure fields
                        chunks = origin.gen_declaration_chunks(self, **kw)
                    else:
                        raise RuntimeError("Attempt to generate chunks for"
                            " local variable '%s'" % origin
                        )
            else:
                chunks = origin.gen_defining_chunk_list(self, **kw)

            # All chunks of the `origin` has been generated at this point.
            self.stack.pop()

            # Note that conversion to a tuple is performed to prevent further
            # modifications of chunk list.
            self.chunk_cache[key] = tuple(chunks)

            # Some `TypeContainer`'s can require extra types when the model is
            # not suitable enough.
            if not foreign:
                for ref in origin.extra_references:
                    referenced_chunks = self.provide_chunks(ref)
                    for chunk in chunks:
                        chunk.add_references(referenced_chunks)
        else:
            if isinstance(origin, Type) and foreign:
                if chunks:
                    # It's HeaderInclusion
                    chunks[0].add_reason(origin)
                # else:
                #     print("reference to %s provided no inclusion" % origin)

        return chunks

    def _gen_foreign_type_chunks(self, foreign_type):
        current = self.definer
        current_references = current.references

        # In a case when declaration and definition of a function are in
        # different files, it is necessary to include the file with
        # the declaration.
        if (    isinstance(foreign_type, Function)
            and foreign_type.declaration is not None
        ):
            foreign_type = foreign_type.declaration

        if foreign_type in current_references:
            return []

        definer = foreign_type.definer

        if current.inherit_references:
            definer_references = set()
            for ref in definer.references:
                # Definer of a `foreign_type`
                # may depend on an inner type (ref) from the `current`
                # file. In this case, inclusion of that `definer`
                # must be placed below the inner type in resulting
                # file. Adding ref to `definer_references` results in the
                # required order among code chunks.
                if ref.definer is current:
                    definer_references.add(ref)
                else:
                    # `definer` of a `foreign_type` may depend on a
                    # foreign type `ref` from another file, which will
                    # be included in the resulting `current` file (since we use
                    # some `other_foreign_type` from it). In this case,
                    # inclusion of that `definer` must be placed below the
                    # inclusion of that another file in the resulting file.
                    for other_foreign_type in current.types.values():
                        if other_foreign_type.definer is current:
                            # it's not foreign
                            continue

                        if other_foreign_type not in current_references:
                            if ref.definer is other_foreign_type.definer:
                                definer_references.add(ref)
                                break
                        # else:
                        #     No file will be included for
                        #     `other_foreign_type`
                    else:
                        current_references.add(ref)
        else:
            definer_references = set(definer.references)

        refs = []
        for r in definer_references:
            ref_chunks = self.provide_chunks(r)

            if not ref_chunks:
                continue

            # not only `HeaderInclusion` can satisfies reference
            if isinstance(ref_chunks[0], HeaderInclusion):
                ref_chunks[0].add_reason(r,
                    kind = "satisfies %s by" % definer
                )

            refs.extend(ref_chunks)

        if definer is CPP:
            chunks = refs
        else:
            inc = HeaderInclusion(definer)
            inc.add_references(refs)
            inc.add_reason(foreign_type)
            chunks = [inc]

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
                if isinstance(frame, Type):
                    definer = frame.definer.path
            except AttributeError:
                pass

            definer = "" if definer is None else ("  (%s)" % definer)

            frames.append("    %-20s %s%s" % (
                type(frame).__name__, frame, definer
            ))
        return "\n".join(frames)


macro_forbidden = compile("[^0-9A-Z_]")

class SourceFile(object):

    def __init__(self, origin,
        protection_prefix = "INCLUDE_"
    ):
        self.name = splitext(basename(origin.path))[0]
        self.is_header = type(origin) is Header
        # Note that, chunk order is significant while one reference per chunk
        # is enough.
        self.chunks = OrderedSet()
        self.sort_needed = False
        self.protection_prefix = protection_prefix
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
                label += "\\n*\\n"
                for r in ch.reasons:
                    label += "%s %s\\l" % r

            # `ch`unk can overwrite default attributes
            appearance = dict(
                label = label
            )
            appearance.update(ch.appearance)

            style = " ".join(
                map('%s="%s"'.__mod__,
                    ((n, v.replace('"', '\\"')) for n, v in appearance.items())
                )
            )

            w.write('\n    %s [%s]\n' % (cnn, style))

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
        chunks = sort_chunks(OrderedSet(sorted(self.chunks)),
            allow_loops = True
        )

        f = open(file_name, "w")
        self.gen_chunks_graph(f, chunks)
        f.close()

    def remove_dup_chunk(self, ch, ch_remove):
        for user in list(ch_remove.users):
            user.del_reference(ch_remove)
            # prevent self references
            if user is not ch:
                user.add_reference(ch)

        for __, _type in ch_remove.reasons:
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
            chunk.source = self
            self.sort_needed = True
            self.chunks.add(chunk)

            # Also add referenced chunks into the source
            for ref in chunk.references:
                self.add_chunk(ref)
        elif not chunk.source == self:
            raise RuntimeError("The chunk %s is already in %s"
                % (chunk.name, chunk.source.name)
            )

    def optimize_inclusions(self,
        graphs_prefix = None,
        log = lambda *args, **kw : None
    ):
        """
:param graphs_prefix:
    is a prefix of the path for dumping intermediate chunk graphs.
    Graphs paths will be `graphs_prefix + ".N.gv"` where N is a serial number.
        """
        log("-= inclusion optimization started for %s.%s =-" % (
            (self.name, "h" if self.is_header else "c")
        ))

        if graphs_prefix is not None:
            N = 0

        # `header_0` -> a header providing inclusion `header_0`
        effective_includers = {}

        # Dictionary is used for fast lookup `HeaderInclusion` by `Header`.
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
                # Initially, each header provides its inclusion by self.
                effective_includers[h] = h

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

            h_provider = effective_includers[h]
            substitution = included_headers[h_provider]

            for sp in h.inclusions:
                s = Header[sp]
                if s in included_headers:
                    # If an originally included header `s` is transitively
                    # included by another one (`h_provider`) then inclusion of
                    # `s` is redundant and must be deleted. All references to
                    # it must be redirected to inclusion of `h_provider`.

                    redundant = included_headers[s]

                    # Because the header inclusion graph is not acyclic,
                    # a header can (transitively) include itself. Then nothing
                    # is to be substituted.

                    if redundant is substitution:
                        log("Cycle: " + s.path)
                        continue

                    if redundant.origin is not s:
                        # inclusion of s was already removed as redundant
                        log("%s includes %s which already substituted by "
                            "%s" % (h_provider.path, s.path,
                                redundant.origin.path
                            )
                        )
                        continue

                    # Because of references between headers, inclusion of `s`
                    # can be required by another header inclusion and
                    # (transitively) by the `substitution` itself.
                    if substitution.after(redundant):
                        log("%s includes %s but substitution creates loop,"
                            " skipping" % (h_provider.path, s.path)
                        )
                        continue

                    log("%s includes %s, substitute %s with %s" % (
                        h_provider.path, s.path, redundant.origin.path,
                        substitution.origin.path
                    ))

                    if graphs_prefix is not None:
                        # Highlight chunks of interest.
                        prev_color = substitution.appearance.get("color")
                        substitution.appearance["color"] = "green"
                        redundant.appearance["color"] = "red"

                        graph_path = graphs_prefix + ".%d.gv" % N
                        N += 1
                        log("Generating " + graph_path)
                        self.gen_chunks_gv_file(graph_path)

                        # Reverting highlighting of removed chunk is useless.
                        if prev_color:
                            substitution.appearance["color"] = prev_color
                        else:
                            del substitution.appearance["color"]

                    self.remove_dup_chunk(substitution, redundant)

                    # The inclusion of `s` was removed but `s` can include
                    # a header (`hdr`) also included by current file.
                    # The inclusion of `hdr` will be removed (like `redundant`)
                    # but its substitution is just removed `redundant`
                    # inclusion. Actually, same `substitution` must be used
                    # instead.
                    # Effective inclusions are kept in `included_headers`.
                    # If `s` has been processed before `h` then
                    # there could be several references to `redundant`
                    # inclusion of `s` in `included_headers`. All of them must
                    # be replaced with currently actual inclusion of `h`.
                    for hdr, chunk in included_headers.items():
                        if chunk is redundant:
                            included_headers[hdr] = substitution

                if s not in effective_includers:
                    stack.append(s)
                    # Now provider of `h` also provides `s`.
                    effective_includers[s] = h_provider

        # if graphs_prefix is not None:
        # Final graph can be printed using another way (`with_chunk_graph`).

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

    def header_paths_shortening(self, include_paths):
        origin_dir = dirname(self.origin.path)

        for ch in self.chunks:
            if not isinstance(ch, HeaderInclusion):
                continue

            if ch.origin.locked_inclusions:
                continue

            header_path = ch.origin.path
            if origin_dir == dirname(header_path):
                path = (basename(header_path),)
            else:
                path = path2tuple(header_path)
                if path[0] in include_paths:
                    path = path[1:]
            ch.path = path

    def generate(self, writer,
        graphs_prefix = None,
        gen_debug_comments = False,
        include_paths = tuple()
    ):
        # check for duplicate chunks for same origin
        self.remove_chunks_with_same_origin()

        self.check_static_function_declarations()

        if self.sort_needed:
            self.chunks = sort_chunks(self.chunks)

        if OPTIMIZE_INCLUSIONS:
            self.optimize_inclusions(graphs_prefix = graphs_prefix)

        self.header_paths_shortening(include_paths)

        # semantic sort
        self.chunks = OrderedSet(sorted(self.chunks))

        if self.sort_needed:
            self.chunks = sort_chunks(self.chunks)

        writer.write(
            "/* %s.%s */\n" % (self.name, "h" if self.is_header else "c")
        )

        if self.is_header and self.protection_prefix is not None:
            writer.write("""\
#ifndef {prefix}{name}_H
#define {prefix}{name}_H
""".format(name = self.name_for_macro(), prefix = self.protection_prefix)
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

        if self.is_header and self.protection_prefix is not None:
            writer.write(
                "#endif /* %s%s_H */\n" % (
                    self.protection_prefix, self.name_for_macro()
                )
            )

    def name_for_macro(self):
        return macro_forbidden.sub('_', self.name.upper())


def sort_chunks(chunks, allow_loops = False):
    new_chunks = OrderedSet()
    # topology sorting
    for chunk in chunks:
        if not chunk.visited == 2:
            depth_first_sort(chunk, new_chunks, allow_loops = allow_loops)

    for chunk in new_chunks:
        chunk.visited = 0

    return new_chunks


def depth_first_sort(chunk, new_chunks, allow_loops = False):
    # visited:
    # 0 - not visited
    # 1 - visited
    # 2 - added to new_chunks
    chunk.visited = 1
    for ch in sorted(chunk.references):
        if ch.visited == 2:
            continue
        if ch.visited == 1:
            if allow_loops:
                continue
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
        depth_first_sort(ch, new_chunks, allow_loops = allow_loops)

    chunk.visited = 2
    new_chunks.add(chunk)


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
                if t.definer is not h:
                    continue
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
