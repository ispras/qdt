__all__ = [
    "remove_file"
  , "fixpath"
  , "path2tuple"
  , "ee"
  , "cli_repr"
]

from os import (
    environ,
    sep,
    name as os_name,
    remove
)
from errno import (
    ENOENT
)
from re import (
    compile
)


def remove_file(file_name):
    try:
        remove(file_name)
    except OSError as e:
        # errno.ENOENT = no such file or directory
        if e.errno != ENOENT:
            print("Error: %s - %s." % (e.filename, e.strerror))

if os_name == "nt":
    drive_letter = compile("(/)([a-zA-Z])($|/.*)")

    def fixpath(path):
        "Fixes UNIX-like paths under Windows normally produced by MSYS."
        mi = drive_letter.match(path)
        if mi:
            tail = mi.group(3)
            if tail:
                tail = sep.join(tail.split("/"))
            else:
                tail = sep
            path = mi.group(2) + ":" + tail

        return path
else:
    fixpath = lambda x : x

re_sep = compile("/|\\\\")

def path2tuple(path):
    "Splits file path by both UNIX and DOS separators returning a tuple."
    parts = re_sep.split(path)
    return tuple(parts)

def ee(env_var, default = "False"):
    """ Evaluate Environment variable.

It's not secure but that library is not about it.
    """
    return eval(environ.get(env_var, default), {})

def cli_repr(obj):
    """ Variant of standard `repr` that returns string suitable for using with
a Command Line Interface, like the one enforced by `bash`. This is designed to
get a `str`. Other input can be incompatible.
    """
    # Replace ' with " because it is for CLI mostly (bash)
    # and there is no difference for Python.
    # Also `repr` replaces ' with \' because it wraps result in '.
    # This function re-wraps result in ", so the replacement must be reverted.
    return '"' + repr(obj).replace('"', r'\"').replace(r"\'", "'")[1:-1] + '"'
