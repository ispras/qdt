__all__ = [
    "execfile"
  , "bstr"
]

from sys import (
    path as py_path
)
from os.path import (
    split
)
from os import (
    getcwd
)
from six import (
    PY3
)
from six.moves import (
    map
)


def execfile(filename, globals = None, locals = None):
    f = open(filename, "rb")
    content = f.read()
    f.close()

    if globals is None:
        globals = {}

    globals["__file__"] = filename
    globals["__name__"] = "__main__"

    file_path = split(filename)[0]

    if not file_path:
        file_path = getcwd()

    new_path = file_path not in py_path

    if new_path:
        py_path.append(file_path)

    try:
        exec(content, globals, locals)
    finally:
        if new_path:
            py_path.remove(file_path)


if PY3:
    def bstr(v):
        if isinstance(v, str):
            return v.encode("utf-8")
        elif isinstance(v, bytes):
            return v
        else:
            raise ValueError("Incorrect value type %s" % type(v))
else:
    def bstr(v):
        if isinstance(v, str):
            return v
        elif isinstance(v, unicode):
            return v.encode("utf-8")
        else:
            raise ValueError("Incorrect value type %s" % type(v))

bstr.__doc__ = "Given a string-like object, returns it as bytes."
" Unicode strings are encoded in UTF-8."
