__all__ = [
    "pypath"
  , "iter_submodules"
  , "pythonpath"
]

from contextlib import (
    contextmanager
)
from os.path import (
    isdir,
    isfile,
    abspath,
    dirname,
    join
)
import sys
from inspect import (
    stack,
    getmodule
)
from os import (
    listdir
)


def iter_submodules():
    cur_dir = dirname(caller_file_name())

    for item in listdir(cur_dir):
        if item[-3:] == ".py":
            name = item[:-3]
            if name != "__init__":
                yield name
        else:
            fullname = join(cur_dir, item)

            if isdir(fullname) and isfile(join(fullname, "__init__.py")):
                yield item


def caller_file_name():
    "Returns name of file defining caller of that function caller."
    # https://stackoverflow.com/questions/13699283/how-to-get-the-callers-filename-method-name-in-python

    # stack[0] - caller_file_name
    # stack[1] - caller of `caller_file_name`
    # stack[2] - caller which file name is requested
    frame = stack()[2]
    module = getmodule(frame[0])
    return module.__file__


def pypath(rel_path):
    """ Configures PYTHONPATH (sys.path) to import custom module version
instead of system version of that module. Path to custom module is
given relative to the directory containing file of caller of this function.
Use it with `with` statement. Relative path must be given with dots as
separators (like relative import).
N dots one by one means (N - 1) returns to parent directory.

Ex.:

with pypath("..sister_directory"):
    # Import custom version of a_module from directory "../sister_directory".
    import a_module

    """

    if rel_path[0] == '.':
        # .dir is same as dir
        rel_path = rel_path[1:]

    cur_dir = dirname(abspath(caller_file_name()))

    parts =  rel_path.split('.')
    for p in parts:
        if p:
            # .folder
            cur_dir = join(cur_dir, p)
        else:
            # ..
            cur_dir = dirname(cur_dir)

    # Caller file name evaluation is separated because usage of
    # contextmanager affects the stack making caller's directory path
    # evaluation a bit harder.
    # Also `setpypath` might be used independently if the caller can evaluate
    # directory name.

    return pythonpath(cur_dir)


@contextmanager
def pythonpath(dirname):
    "Prepend PYTHONPATH with `dirname` for the time of a `with` block."

    # See here about how this context manager works.
    # https://jeffknupp.com/blog/2016/03/07/python-with-context-managers/

    if dirname in sys.path:
        yield
    else:
        sys.path.insert(0, dirname)
        yield
        sys.path.remove(dirname)
