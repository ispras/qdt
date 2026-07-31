__all__ = [
    "rpath2path"
  , "path2rpath"
]

from common import (
    path2tuple,
)

from os.path import (
    join,
)


def rpath2path(rpath, encoding = "utf-8"):
    return join(*reversed(tuple(
        (p if isinstance(p, str) else p.decode(encoding)) for p in rpath
    )))

def path2rpath(path):
    return tuple(reversed(path2tuple(path)))
