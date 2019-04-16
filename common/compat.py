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

    code = compile(content, filename, "exec")

    with pythonpath(file_path):
        exec(code, globals, locals)
