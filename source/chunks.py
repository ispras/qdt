"Source code instances"

__all__ = [
    "SourceChunk"
      # Subclasses are for internal usage
  , "ANC"
  , "CAN"
  , "NBS"
  , "NSS"
]

from re import (
    compile,
)
from itertools import (
    chain,
)
from common import (
    ee,
    path2tuple,
    OrderedSet,
)
from .code_gen_helpers import (
    gen_init_string,
    gen_function_declaration_string,
)


# Coding style settings
APPEND_NL_AFTER_HEADERS = not ee("QDT_NO_NL_AFTER_HEADERS")
APPEND_NL_AFTER_MACROS = not ee("QDT_NO_NL_AFTER_MACROS")


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

    def after(self, another):
        "This chunk is after `another` one if a path of `references` exists."
        stack = list(self.references)
        visited = set()
        while stack:
            c = stack.pop()
            if c is another:
                return True

            if c in visited:
                continue

            visited.add(c)
            stack.extend(c.references)

        return False

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
            clear_line = re_clr.sub("\\1", re_anc.sub("\\1", re_can.sub("\\1",
                         re_nbs.sub("\\1 ", re_nss.sub("\\1 ", line)))))

            if len(clear_line) <= max_cols:
                code += clear_line
                if idx1 != last_line:
                    code += '\n'
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

            if idx1 != last_line:
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
            "Header %s inclusion" % header,
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
            "%s#define %s%s%s\n" % (
                indent,
                macro.c_name,
                args_txt,
                "" if macro.text is None else (" %s" % macro.text)
            )
        )


class MacroTypeChunk(SourceChunk):

    def __init__(self, _type, indent = ""):
        super(MacroTypeChunk, self).__init__(_type,
            "Usage of type %s" % _type,
            code = (indent + _type.macro.gen_usage_string(_type.initializer)
                + "\n"
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

    def __init__(self, var,
        indent = "",
        append_nl = True,
        separ = ";"
    ):
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


class StructureOpeningBracket(SourceChunk):

    def __init__(self, struct, append_nl = True):
        super(StructureOpeningBracket, self).__init__(struct,
            "Opening bracket of structure %s declaration" % struct,
            "@b{" + ("\n" if append_nl else "")
        )


class StructureClosingBracket(SourceChunk):

    def __init__(self, struct, indent = ""):
        super(StructureClosingBracket, self).__init__(struct,
            "Closing bracket of structure %s declaration" % struct,
            indent + "}"
        )


class StructureTypedefDeclarationBegin(SourceChunk):

    def __init__(self, struct, indent = ""):
        super(StructureTypedefDeclarationBegin, self).__init__(struct,
            "Beginning of structure %s declaration" % struct,
            """\
{indent}typedef@bstruct@b{struct_name}""".format(
    indent = indent,
    struct_name = struct.c_name
            )
        )


class StructureTypedefDeclarationEnd(SourceChunk):
    weight = 2

    def __init__(self, struct,
        append_nl = True
    ):
        super(StructureTypedefDeclarationEnd, self).__init__(struct,
            "Ending of structure %s declaration" % struct,
            """\
@b{struct_name};{nl}
""".format(
    struct_name = struct.c_name,
    nl = "\n" if append_nl else ""
            )
        )


class StructureDeclarationBegin(SourceChunk):

    def __init__(self, struct, indent = ""):
        super(StructureDeclarationBegin, self).__init__(struct,
            "Beginning of structure %s declaration" % struct,
            """\
{indent}struct{struct_name}""".format(
    indent = indent,
    struct_name = ("@b" + struct.c_name) if struct.is_named else ""
            )
        )


class StructureDeclarationEnd(SourceChunk):
    weight = 2

    def __init__(self, struct,
        append_nl = True
    ):
        super(StructureDeclarationEnd, self).__init__(struct,
            "Ending of structure %s declaration" % struct,
            ";" + ("\n" if append_nl else "") + "\n"
        )


class StructureVariableDeclarationBegin(SourceChunk):

    def __init__(self, var, indent = ""):
        super(StructureVariableDeclarationBegin, self).__init__(var,
            "Beginning of nameless structure variable %s declaration" % var,
            indent + "struct"
        )


class StructureVariableDeclarationEnd(SourceChunk):
    weight = 4

    def __init__(self, var, append_nl = True):
        super(StructureVariableDeclarationEnd, self).__init__(var,
            "Ending of nameless structure variable %s declaration" % var,
            """\
@b{name};{nl}""".format(
    name = var.name,
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


class FunctionDeclaration(SourceChunk):
    weight = 6

    def __init__(self, function, indent = ""):
        super(FunctionDeclaration, self).__init__(function,
            "Declaration of function %s" % function,
            "%s;\n" % gen_function_declaration_string(indent, function)
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

    def __init__(self, origin, indent = ""):
        name = "Opaque code named %s" % origin

        super(OpaqueChunk, self).__init__(origin, name,
            indent + str(origin.code)
        )

        # Ordering weight can be overwritten.
        if origin.weight is not None:
            self.weight = origin.weight
