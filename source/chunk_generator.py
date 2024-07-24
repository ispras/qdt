__all__ = [
    "ChunkGenerator"
]

from .chunks import (
    HeaderInclusion,
)
from .function.bindings import (
    BodyTree,
)
from .function.var_declarator import (
    VarDeclarator,
)
from .model import (
    CPP,
    Function,
    Structure,
    Type,
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
            protection_prefix = definer.protection_prefix,
        )

        inherit_references = definer.inherit_references
        if inherit_references:
            assert (isinstance(definer, Header))

        # Auto `Declare` variables in `Function`s with `BodyTree`.
        for func in definer.types.values():
            if not isinstance(func, Function):
                continue
            if func.definer is not definer:
                continue
            body = func.body
            if not isinstance(body, BodyTree):
                continue
            VarDeclarator(body, func.args).visit()

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
