__all__ = [
    "pypath"
]

from contextlib import (
    contextmanager
)
from os.path import (
    abspath,
    dirname,
    join
)
import sys
from inspect import (
    stack,
    getmodule
)

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
    # https://stackoverflow.com/questions/13699283/how-to-get-the-callers-filename-method-name-in-python
    frame = stack()[1]
    module = getmodule(frame[0])
    return _pypath(module.__file__, rel_path)

@contextmanager
def _pypath(caller_file_name, rel_path):
    """ Caller file name evaluation is moved to a wrapper because usage of
contextmanager affects the stack making caller's directory path evaluation a
bit harder.
    """
    if rel_path[0] == '.':
        # .dir is same as dir
        rel_path = rel_path[1:]

    cur_dir = dirname(abspath(caller_file_name))

    parts =  rel_path.split('.')
    for p in parts:
        if p:
            # .folder
            cur_dir = join(cur_dir, p)
        else:
            # ..
            cur_dir = dirname(cur_dir)

    # Setup PYTHONPATH for the time of `with` block.
    # See here about how this context manager works.
    # https://jeffknupp.com/blog/2016/03/07/python-with-context-managers/
    if cur_dir in sys.path:
        yield
    else:
        sys.path.insert(0, cur_dir)
        yield
        sys.path.remove(cur_dir)
