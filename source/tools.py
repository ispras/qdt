__all__ = [
    "line_origins"
  , "get_cpp_search_paths"
  , "get_gcc_defines_raw"
  , "iter_gcc_defines"
]

from common import (
    OrderedSet,
)

from re import (
    compile,
)
from subprocess import (
    Popen,
    PIPE
)
from sys import (
    version_info as py_version
)

re_define = compile(br"#\s*define\s+")


def line_origins(origins):
    """ Adds extra references to origins so the chunks of first one will be to
    the top of chunks of second one, and so on. """
    oiter = iter(origins)
    prev = next(oiter)

    for cur in oiter:
        try:
            refs = cur.extra_references
        except AttributeError:
            cur.extra_references = {prev}
        else:
            refs.add(prev)
        prev = cur

def get_cpp_search_paths():
    cpp = Popen(["cpp", "-v", "-"], stdout = PIPE, stderr = PIPE, stdin = PIPE)
    # Passing None input results in closing of stdin internally by Popen.
    __, err = cpp.communicate(input = None)

    if cpp.returncode:
        raise RuntimeError("Cannot get default cpp search paths\n" + err)

    # Note that verbose info is printed in stderr.
    lines = err.splitlines()
    liter = iter(lines)

    # skip unnecessary lines
    for l in liter:
        if l.startswith(b"#include <...>"):
            break

    # Order of -I may alter preprocessing result.
    # At least, any randomization must be avoided.
    paths = OrderedSet()
    for l in liter:
        # All include paths are indented but list terminator is not:
        # ^End of search list.
        if not l.startswith(b" "):
            break
        raw = l.strip()
        p = raw.decode("utf8") if py_version[0] != 2 else raw
        paths.add(p)

    return tuple(paths)


def get_gcc_defines_raw():
    gcc = Popen(["gcc", "-dM", "-E", "-"],
        stdout = PIPE,
        stderr = PIPE,
        stdin = PIPE,
    )

    out, err = gcc.communicate(input = None)

    if gcc.returncode:
        raise RuntimeError("Cannot get default gcc defines\n" + err)

    return out


def iter_gcc_defines():
    return (re_define.sub(b"", l) for l in get_gcc_defines_raw().splitlines())
