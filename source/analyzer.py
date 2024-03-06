__all__ = [
    "co_build_inclusions"
]


from common import (
    path2tuple,
    pypath,
)
from .model import (
    Macro,
    Type,
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
from .source_file import (
    Header,
)
from .tools import (
    get_cpp_search_paths,
)

from os import (
    listdir,
)
from os.path import (
    isdir,
    join,
    splitext,
)
import sys


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


if sys.version_info.major < 3:
    def read_include_file(filepath):
        with open(filepath) as file:
            return file.read()
else:
    def read_include_file(filepath):
        with open(filepath, 'r',
            encoding='utf-8',
            errors='surrogateescape'
        ) as file:
            return file.read()


def _on_include(includer, inclusion, is_global):
    if path2tuple(inclusion) not in Header.reg:
        print("Info: parsing " + inclusion + " as inclusion")
        h = Header(path = inclusion, is_global = is_global)
        h.parsed = True
    else:
        h = Header[inclusion]

    Header[includer].add_inclusion(h)


class _MacrosCatcher(dict):

    def __init__(self, cpp):
        dict.__init__(self)
        self._cpp = cpp
        self.update(cpp.macros)
        cpp.macros = self

    def __setitem__(self, name, macro):
        dict.__setitem__(self, name, macro)
        try:
            definer = self._cpp.source
        except AttributeError:
            return
        _on_define(definer, macro)


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


def _build_inclusions(start_dir, prefix, recursive):
    full_name = join(start_dir, prefix)
    if isdir(full_name):
        if not recursive:
            return
        for entry in listdir(full_name):
            yield _build_inclusions(
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

                p.on_include = _on_include
                p.all_inclusions = True
                # Avoid `ply.cpp.Preprocessor` modification.
                _MacrosCatcher(p)

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

                yields_per_header.append(yields_per_current_header)


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

    global yields_per_header
    yields_per_header = []

    if not isinstance(sys.stdout, ParsePrintFilter):
        sys.stdout = ParsePrintFilter(sys.stdout)

    for h in Header.reg.values():
        h.parsed = False

    for path, recursive in include_paths:
        dname = join(work_dir, path)
        for entry in listdir(dname):
            yield _build_inclusions(dname, entry, recursive)

    for h in Header.reg.values():
        del h.parsed

    sys.stdout = _sys_stdout_recovery

    yields_total = sum(yields_per_header)

    if yields_total:
        print("""Header inclusions build statistic:
Yields total: %d
Max yields per header: %d
Min yields per header: %d
Average yields per header: %f
""" % (
yields_total,
max(yields_per_header),
min(yields_per_header),
yields_total / float(len(yields_per_header))
)
        )
    else:
        print("Headers not found")

    del yields_per_header
