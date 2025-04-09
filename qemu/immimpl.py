__all__ = [
    "ImmImplType"
]

from common import (
    mlget as _,
    path2tuple,
)
from .qom import (
    QOMType,
)
from .qom_desc import (
    describable,
)
from source import (
    Source,
    Header,
    OpaqueCode,
)

from collections import (
    OrderedDict,
)
from os import (
    listdir,
)
from os.path import (
    basename,
    isdir,
    isfile,
    join,
)
from re import (
    compile,
)


re_hdr_name = compile("(.*[.]h$)|(.*[.]inc(([.].*)|$))")

@describable
class ImmImplType(QOMType):
    """ Immediate Implementation.
Not a QOM type.
It's a way to embed arbitrary sources.
    """

    __attribute_info__ = OrderedDict((
        ("path", { "short": _("Path"), "input": str }),
        ("gen_order", # Used by QOMDescription.
            { "short": _("Generation Order"), "input": int }
        ),
    ))

    def __init__(self, name, directory,
        path = ".",
        gen_order = 0,
        **__
    ):
        """
@param name:
    For user convenience only.

@param directory:
    A directory in Qemu source tree, the implementation is to be embedded.

@param path:
    A path relative to the project or absolute to the implementation file or
    directory.

@param gen_order:
    Less values are generated earlier.
        """
        self.name = name
        self.directory = directory
        self.path = path
        self.gen_order = gen_order

    def co_gen_sources(self):
        self._sources = sources = []

        path = self.path
        ospath = self.project.lookup_path(self.path)
        base_infix = path2tuple(self.directory)
        base_infix_sz = len(base_infix)

        if isdir(ospath):
            # The implementation source root directory itself is not
            # copied to Qemu directory.
            stack = list(
                (join(ospath, iname), base_infix)
                        for iname in listdir(ospath)
            )
        else:
            stack = [(ospath, base_infix)]

        pop = stack.pop
        extend = stack.extend

        while stack:
            ospath, infix = pop()

            if isfile(ospath):
                with open(ospath, "r") as f:
                    code = f.read()

                name = basename(ospath)
                infixed_nane = infix + (name,)
                qpath = join(*infixed_nane)

                code_wrp = OpaqueCode(code,
                    name = (
                        "code_from#"
                      + join(path, *infixed_nane[base_infix_sz:])
                    ),
                )

                kw = dict(
                    origin = self,
                    path = qpath,
                    locked_inclusions = True,
                    name_comment = False,
                    chunk_group_separator = "",
                )
                if re_hdr_name.match(name.lower()):
                    SourceType = Header
                    kw["is_global"] = False
                    kw["protection_prefix"] = None
                else:
                    SourceType = Source

                source = SourceType(**kw)
                source.add_type(code_wrp)
                sources.append(source)
                continue

            if isdir(ospath):
                name = basename(ospath)
                extend(
                    (join(ospath, iname), infix + (name,))
                        for iname in listdir(ospath)
                )
                continue

            print("%s: unsupported immediate implementation path" % (ospath,))
