__all__ = [
    "execfile"
]

from .pypath import (
    abspath,
    pythonpath
)
from os.path import (
    dirname
)


def execfile(filename, globals = None, locals = None):
    with open(filename, "rb") as f:
        content = f.read()

    if globals is None:
        globals = {}

    globals["__file__"] = filename
    globals["__name__"] = "__main__"

    file_path = abspath(dirname(filename))

    with pythonpath(file_path):
        exec(content, globals, locals)
