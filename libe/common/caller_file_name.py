__all__ = [
    "caller_file_name"
]

from inspect import (
    getmodule,
    stack,
)


def caller_file_name():
    "Returns name of file defining caller of that function caller."
    # https://stackoverflow.com/questions/13699283/how-to-get-the-callers-filename-method-name-in-python

    # stack[0] - caller_file_name
    # stack[1] - caller of `caller_file_name`
    # stack[2] - caller which file name is requested
    frame = stack()[2]
    module = getmodule(frame[0])
    return module.__file__
