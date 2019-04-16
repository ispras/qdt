__all__ = [
    "execfile"
  , "HelpFormatter"
]

from .pypath import (
    abspath,
    pythonpath
)
from os.path import (
    dirname
)

from argparse import (
    ArgumentDefaultsHelpFormatter,
    _CountAction,
    _StoreConstAction
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


class HelpFormatter(ArgumentDefaultsHelpFormatter):
    """ Like `ArgumentDefaultsHelpFormatter` but it does not print defaults
for flags.
    """

    def _get_help_string(self, action):
        if isinstance(action, (_CountAction, _StoreConstAction)):
            return action.help
        return super(HelpFormatter, self)._get_help_string(action)
