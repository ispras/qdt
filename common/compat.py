__all__ = [
    "execfile"
  , "bstr"
  , "charcodes"
  , "characters"
]

from .pypath import (
    abspath,
    pythonpath
)
from os.path import (
    dirname
)

from six import (
    PY3
)
from six.moves import (
    map
)


def execfile(filename, globals = None, locals = None):
    with open(filename, "rb") as f:
        content = f.read()

    if globals is None:
        globals = {}

    globals["__file__"] = filename
    globals["__name__"] = "__main__"

    file_path = abspath(dirname(filename))

    code = compile(content, filename, "exec")

    with pythonpath(file_path):
        exec(code, globals, locals)


if PY3:
    def bstr(v):
        if isinstance(v, str):
            return v.encode("utf-8")
        elif isinstance(v, bytes):
            return v
        else:
            raise ValueError("Incorrect value type %s" % type(v))

    charcodes = lambda _bstr: iter(_bstr)
    characters = lambda _bstr: map(chr, _bstr)
else:
    def bstr(v):
        if isinstance(v, str):
            return v
        elif isinstance(v, unicode):
            return v.encode("utf-8")
        else:
            raise ValueError("Incorrect value type %s" % type(v))

    charcodes = lambda _bstr: map(ord, _bstr)
    characters = lambda _bstr: iter(_bstr)

bstr.__doc__ = "Given a string-like object, returns it as bytes."
" Unicode strings are encoded in UTF-8."
charcodes.__doc__ = "Given bytes, iterates them as integers."
characters.__doc__ = "Given bytes, iterates them as one character strings."
