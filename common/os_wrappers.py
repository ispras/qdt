__all__ = [
    "remove_file"
  , "rename_replacing"
  , "fixpath"
  , "path2tuple"
  , "ee"
  , "bsep"
  , "cli_repr"
  , "bind_all_mouse_wheel"
  , "bind_mouse_wheel"
  , "makedirs"
]

from os import (
    rename,
    environ,
    sep,
    name as os_name,
    remove
)
from os.path import (
    exists,
    isfile,
    isdir
)
from shutil import (
    rmtree
)
from errno import (
    ENOENT
)
from re import (
    compile
)
from .compat import (
    bstr
)
from platform import (
    system
)
from six import (
    PY2
)
from os import (
    makedirs
)
if PY2:
    from os.path import (
        split,
        exists
    )
    from os import (
        mkdir
    )
    from errno import (
        EEXIST
    )

    py2_makedirs = makedirs

    def makedirs(name, mode = 0o777, exist_ok = False):
        "Py3 makedirs emulation for Py2"
        if not exist_ok:
            return py2_makedirs(name, mode)

        head, tail = split(name)
        if not tail:
            head, tail = split(head)
        if head and tail and not exists(head):
            try:
                makedirs(head, mode, exist_ok = True)
            except OSError as e:
                # be happy if someone already created the path
                if e.errno != EEXIST:
                    raise
            if tail == ".": # xxx/newdir/. exists if xxx/newdir exists
                return
        if not exists(name) or not exist_ok:
            # If name exists and it is not "ok", then call `mkdir` because it
            # raises the appropriate exception.
            mkdir(name, mode)


# OS file path separator in binary type
bsep = bstr(sep)



def remove_file(file_name):
    try:
        remove(file_name)
    except OSError as e:
        # errno.ENOENT = no such file or directory
        if e.errno != ENOENT:
            print("Error: %s - %s." % (e.filename, e.strerror))


def rename_replacing(src, dst, *a, **kw):
    """ os.rename works differently under Py2 & Py3 if destination exists.
It's a portable wrapper.
    """

    if isdir(dst):
        rmtree(dst)
    elif isfile(dst):
        remove(dst)
    elif exists(dst):
        raise NotImplementedError(
            "Can't clean the destination " + dst
        )

    return rename(src, dst, *a, **kw)


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


# Binding to mouse wheel, see
# https://stackoverflow.com/questions/17355902/python-tkinter-binding-mousewheel-to-scrollbar
OS = system()
if OS == "Linux":
    def wrap_wheel_handler(handler):
        def scroll_up(e):
            "<ButtonPress-4>"
            e.delta = 1
            handler(e)
        yield scroll_up

        def scroll_down(e):
            "<ButtonPress-5>"
            e.delta = -1
            handler(e)
        yield scroll_down

elif OS == "Windows":
    def wrap_wheel_handler(handler):
        def scale(e):
            "<MouseWheel>"
            # This divisor is tested on:
            # - Windows 7 SP 1 x64
            # - Windows 10 1709 x64
            e.delta //= 120
            handler(e)
        yield scale

else:
    def wrap_wheel_handler(*__):
        return tuple()

    from sys import ( # required only here
        stderr
    )
    stderr.write("bind_all_mouse_wheel is not implemented for %s\n" % OS)

def bind_all_mouse_wheel(w, handler, add = None):
    for h in wrap_wheel_handler(handler):
        w.bind_all(h.__doc__, h, add = add)

def bind_mouse_wheel(w, handler, add = None):
    for h in wrap_wheel_handler(handler):
        w.bind(h.__doc__, h, add = add)
