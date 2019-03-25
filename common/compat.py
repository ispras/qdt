__all__ = [
    "execfile"
  , "HelpFormatter"
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
from argparse import (
    ArgumentDefaultsHelpFormatter,
    _CountAction,
    _StoreConstAction
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


class HelpFormatter(ArgumentDefaultsHelpFormatter):
    """ Like `ArgumentDefaultsHelpFormatter` but it does not print defaults
for flags.
    """

    def _get_help_string(self, action):
        if isinstance(action, (_CountAction, _StoreConstAction)):
            return action.help
        return super(HelpFormatter, self)._get_help_string(action)
