__all__ = [
    "ChunkGenerator"
]

from .chunks import (
    EnumerationDeclarationBegin,
    EnumerationDeclarationEnd,
    EnumerationElementDeclaration,
    FunctionDeclaration,
    FunctionDefinition,
    FunctionPointerDeclaration,
    FunctionPointerTypeDeclaration,
    HeaderInclusion,
    MacroDefinition,
    MacroTypeChunk,
    OpaqueChunk,
    PointerTypeDeclaration,
    StructureClosingBracket,
    StructureDeclarationBegin,
    StructureDeclarationEnd,
    StructureForwardDeclaration,
    StructureTypedefDeclarationBegin,
    StructureTypedefDeclarationEnd,
    StructureOpeningBracket,
    StructureVariableDeclarationBegin,
    StructureVariableDeclarationEnd,
    VariableDeclaration,
    VariableDefinition,
)
from common import (
    DictStack,
    ee,
)
from .function.bindings import (
    BodyTree,
)
from .function.var_declarator import (
    VarDeclarator,
)
from .late import (
    LateLinker,
)
from .model import (
    CPP,
    CPPMacro,
    Enumeration,
    EnumerationElement,
    Function,
    GlobalsCollector,
    Macro,
    MacroUsage,
    OpaqueCode,
    Pointer,
    Structure,
    Type,
    TypesCollector,
    Variable,
)
from .source_file import (
    Header,
    Source,
    SourceFile,
    TypeFixerVisitor,
)

from collections import (
    deque,
)
from inspect import (
    getmro,
)


# Add a new line after the opening curly bracket in the structure without
# fields
ADD_NL_IN_EMPTY_STRUCTURE = ee("QDT_ADD_NL_IN_EMPTY_STRUCTURE", "False")


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

    def generate(self):
        definer = self.definer

        Header.propagate_references()

        file = SourceFile(definer,
            name_comment = definer.name_comment,
            chunk_group_separator = definer.chunk_group_separator,
            protection_prefix = definer.protection_prefix,
        )

        inherit_references = definer.inherit_references
        if inherit_references:
            assert (isinstance(definer, Header))

        # Final late linkage.
        # Some type can be added before types it `Late`-refers are created.
        # So, LateLinker did not resolve them during `add_type`.
        # At moment of `generate` all types must be created.
        glob_ns = DictStack(Type.reg)
        for h in Header.reg.values():
            glob_ns.update(h.global_variables)
        glob_ns.update(definer.types)
        glob_ns.update(definer.global_variables)

        LateLinker(definer, glob_ns = glob_ns).visit()

        # `Late` can be replaced with definer-less types.
        # `TypeFixerVisitor` below will grab them.
        # They, of cource, are not handled by `LateLinker` above.
        # But, they will be handled by `LateLinker` in `add_type` called by
        # `TypeFixerVisitor` below.
        # `TypeFixerVisitor` in `add_type` makes recursion grabbing rest
        # definer-less types and resolving rest `Late` references.

        # This header includes other headers to provide types for includers
        # of self. This is list of references to those types.
        ref_list = []

        if isinstance(definer, Header) and not definer.locked_inclusions:
            for user in definer.includers:
                for ref in user.references:
                    if ref.definer not in user.inclusions:
                        ref_list.append(ref)

        # Finally, we must fix types just before generation because user can
        # change already added types.
        TypeFixerVisitor(definer, definer).visit()

        # Auto `Declare` variables in `Function`s with `BodyTree`.
        # Note that, `TypeFixerVisitor` may grab `definer`-less `Function`s.
        # So, do auto `Variable` declaration after it.
        for func in definer.types.values():
            if not isinstance(func, Function):
                continue
            if func.definer is not definer:
                continue
            body = func.body
            if not isinstance(body, BodyTree):
                continue
            VarDeclarator(body, func.args).visit()
            LateLinker(body).visit()

        for t in definer.types.values():
            if t.definer is definer:
                self.provide_chunks(t)

        for gv in definer.global_variables.values():
            self.provide_chunks(gv)

        if isinstance(definer, Header):
            for r in ref_list:
                self.provide_chunks(r)

        file.add_chunks(self.get_all_chunks())

        return file

    def provide_chunks(self, origin, **kw):
        try:
            return self._provide_chunks(origin, **kw)
        except:
            # This adds extra debug information to first exception message.
            raise RuntimeError("%s %s: failed to provide chunks" % (
                origin, type(origin)
            ))

    def _provide_chunks(self, origin, **kw):
        """ Given origin the method returns chunk list generating it on first
        access. """
        current = self.definer

        while True: # Not a loop
            if isinstance(origin, Variable):
                if origin.declarer is current or origin.definer is current:
                    # A global variable, declared or defined here.
                    key = origin
                    foreign = False
                    break
                if origin.declarer is not None:
                    # A global variable, declared outside.
                    key = origin.declarer
                    foreign = True
                    break
                if origin.definer is None:
                    # It is a variable inside something.
                    key = origin
                    foreign = False
                    break
                raise RuntimeError("Variable '%s' is only defined"
                    " in '%s' but not declared in any header" % (
                        origin, origin.definer.path
                    )
                )

            if isinstance(origin, Type):
                if (    origin.definer is not current
                    # Note, it can be a type inside another type.
                    and isinstance(origin.definer, Source)
                ):
                    key = origin.definer
                    foreign = True
                else:
                    key = origin
                    foreign = False
                break
        else:
            raise ValueError(repr(origin))

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
            elif isinstance(origin, Variable):
                if origin.definer is not None or origin.declarer is not None:
                    # It is a global variable

                    if foreign:
                        try:
                            chunks = self.chunk_cache[key]
                        except KeyError:
                            chunks = [
                                HeaderInclusion(key).add_reason(origin,
                                    kind = "declares"
                                )
                            ]
                    else:
                        # Assume that,
                        # a variable in a header is either `extern` (defined
                        # outside of the header) or `static` ("inlined" in
                        # the header).
                        if self.for_header and not origin.static:
                            kw["extern"] = True
                            chunks = gen_variable_declaration_chunks(
                                origin, self, **kw
                            )
                        else:
                            chunks = get_variable_definition_chunks(
                                origin, self, **kw
                            )
                else:
                    # It is a variable inside something
                    if (    len(self.stack) > 1
                        and isinstance(self.stack[-2], (Structure, Variable))
                    ):
                        # structure fields
                        chunks = gen_variable_declaration_chunks(
                            origin, self, **kw
                        )
                    else:
                        raise RuntimeError("Attempt to generate chunks for"
                            " local variable '%s'" % origin
                        )
            else:
                chunks = self.gen_defining_chunk_list(origin, **kw)

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

    def gen_defining_chunk_list(self, t, **kw):
        if t.base:
            return []
        else:
            return self.gen_chunks(t, **kw)

    def gen_chunks(self, t, **kw):
        for tt in getmro(type(t)):
            gen = get_chunks_generator(tt)
            if gen is not None:
                break
        else:
            raise ValueError("Attempt to generate source chunks for stub"
                " type %s" % t
            )
        return gen(t, self, **kw)


def gen_cpp_macro_chunks(cppm, generator, **__):
    # CPPMacro does't require referenced types
    # because it's defined by C preprocessor.
    return []


def gen_enumeration_chunks(e, generator,
    fields_indent = "    ",
    indent = "",
    **__
):
    enum_begin = EnumerationDeclarationBegin(e, indent)
    enum_end = EnumerationDeclarationEnd(e, indent)

    field_indent = indent + fields_indent
    field_refs = []
    top_chunk = enum_begin

    last_num = len(e.elems) - 1
    for i, f in enumerate(e.elems.values()):
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


def gen_enumeration_element_chunks(e, generator, **kw):
    return list(generator.provide_chunks(e.enum_parent, **kw))


def gen_function_declaration_chunks(f, generator,
    indent = "",
    **__
):
    ch = FunctionDeclaration(f, indent)

    refs = gen_function_decl_ref_chunks(f, generator)

    ch.add_references(refs)

    return [ch]


def gen_function_definition_chunks(f, generator,
    indent = "",
    **__
):
    ch = FunctionDefinition(f, indent)

    refs = (gen_function_decl_ref_chunks(f, generator) +
        gen_function_def_ref_chunks(f, generator)
    )

    ch.add_references(refs)
    return [ch]


def gen_function_chunks(f, generator,
    **kw
):
    if f.static and f.inline:
        return gen_function_definition_chunks(f, generator, **kw)
    if generator.for_header:
        return gen_function_declaration_chunks(f, generator, **kw)
    else:
        return gen_function_definition_chunks(f, generator, **kw)


def gen_macro_chunks(m, generator, **__):
    return [ MacroDefinition(m) ]


def gen_macro_usage_chunks(mu, generator,
    indent = "",
    **__
):
    macro = mu.macro
    initializer = mu.initializer

    refs = list(generator.provide_chunks(macro))

    if initializer is not None:
        for v in initializer.used_variables:
            refs.extend(generator.provide_chunks(v))

        for t in initializer.used_types:
            refs.extend(generator.provide_chunks(t))

    if mu.is_named:
        ch = MacroTypeChunk(mu, indent)
        ch.add_references(refs)
        return [ch]
    else:
        return refs


def gen_opaque_code_chunks(self, generator,
    indent = "",
    **__
):
    ch = OpaqueChunk(self, indent)

    for item in self.used:
        ch.add_references(generator.provide_chunks(item))

    return [ch]


def gen_pointer_chunks(p, generator, **__):
    _type = p.type

    is_function = isinstance(_type, Function)

    # strip function definition chunk, its references is only needed
    if is_function:
        refs = gen_function_decl_ref_chunks(_type, generator)
    else:
        refs = generator.provide_chunks(_type)

    if not p.is_named:
        return refs

    name = p.c_name

    if is_function:
        ch = FunctionPointerTypeDeclaration(_type, name)
    else:
        ch = PointerTypeDeclaration(_type, name)

    """ 'typedef' does not require referenced types to be visible.
Hence, it is not correct to add references to the PointerTypeDeclaration
chunk. The references is to be added to `users` of the 'typedef'.
    """
    ch.add_references(refs)

    return [ch]


def gen_structure_chunks(s, g,
    indent = "",
    **__
):
    if not s.is_named:
        raise AssertionError("chunks for a nameless structure are "
            "generated by the variable having that structure immediately "
            "in its declaration"
        )

    if s._definition is not None:
        return [StructureForwardDeclaration(s, indent)]

    if s.declaration is None:
        struct_begin = StructureTypedefDeclarationBegin(s, indent)
        struct_end = StructureTypedefDeclarationEnd(s)
    else:
        struct_begin = StructureDeclarationBegin(s, indent)
        struct_end = StructureDeclarationEnd(s)

    gen_structure_fields_chunks(s, g, struct_begin, struct_end, indent)

    return [struct_end, struct_begin]

def gen_structure_fields_chunks(s, generator, struct_begin, struct_end,
    indent = "",
    **__
):
    fields_indent = "    "
    need_nl = ADD_NL_IN_EMPTY_STRUCTURE or bool(s.fields)

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

    br = StructureOpeningBracket(s, need_nl)
    br.add_reference(struct_begin)
    top_chunk = br

    for f in s.fields.values():
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

    br = StructureClosingBracket(s, indent if need_nl else "")
    br.add_reference(top_chunk)
    struct_end.add_reference(br)


def gen_variable_declaration_chunks(v, generator,
    indent = "",
    extern = False,
    **__
):
    type_ = v.type
    if (    isinstance(type_, Structure)
        and not type_.is_named
    ):
        var_begin = StructureVariableDeclarationBegin(v, indent)
        var_end = StructureVariableDeclarationEnd(v)
        gen_structure_fields_chunks(type_, generator, var_begin, var_end, indent)
        return [var_end, var_begin]
    elif (    isinstance(type_, Pointer)
          and not type_.is_named
          and isinstance(type_.type, Function)
    ):
        ch = FunctionPointerDeclaration(v, indent, extern)
        refs = gen_function_decl_ref_chunks(type_.type, generator)
    else:
        ch = VariableDeclaration(v, indent, extern)
        refs = generator.provide_chunks(type_)
    ch.add_references(refs)

    return [ch]

def get_variable_definition_chunks(v, generator,
    indent = "",
    append_nl = True,
    separ = ";",
    **__
):
    ch = VariableDefinition(v, indent, append_nl, separ)

    refs = list(generator.provide_chunks(v.type))

    if v.initializer is not None:
        for v in v.initializer.used_variables:
            refs.extend(generator.provide_chunks(v))

        for t in v.initializer.used_types:
            refs.extend(generator.provide_chunks(t))

    ch.add_references(refs)
    return [ch]


CHUNK_GENERATORS = {
    CPPMacro: gen_cpp_macro_chunks,
    Enumeration: gen_enumeration_chunks,
    EnumerationElement: gen_enumeration_element_chunks,
    Function: gen_function_chunks,
    Macro: gen_macro_chunks,
    MacroUsage: gen_macro_usage_chunks,
    OpaqueCode: gen_opaque_code_chunks,
    Pointer: gen_pointer_chunks,
    Structure: gen_structure_chunks,
}

get_chunks_generator = CHUNK_GENERATORS.get


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
