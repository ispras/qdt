__all__ = [
    "FunctionArgument"
  , "LateLinker"
]

from ..model import (
    NodeVisitor,
)
from six import (
    integer_types,
)


class FunctionArgument(object):
    """ A placeholder for an argument of a function. It will be replaced with
the `Variable` representing the argument.
    """

    def __init__(self, ref):
        """
:param ref:
    A reference to an argument: either `str`ing or `int`eger index.
        """
        self.ref = ref


class LateLinker(NodeVisitor):

    def __init__(self, root, function):
        super(LateLinker, self).__init__(root)
        self.function = function

    def on_visit(self):
        cur = self.cur
        if not isinstance(cur, FunctionArgument):
            return

        ref = cur.ref
        args = self.function.args

        if isinstance(ref, str):
            for arg in args:
                if arg.name == ref:
                    break
            else:
                raise RuntimeError("Function %s has no argument '%s'" % (
                    self.function, ref
                ))
        elif isinstance(ref, integer_types):
            try:
                arg = args[ref]
            except IndexError:
                raise RuntimeError("Incorrect argument index %d. Function %s"
                    " has %u arguments"% (ref, self.function, len(args))
                )
        else:
            raise RuntimeError("Unsupported type (%s) of function (%s)"
                " argument reference (%s)" % (type(ref), self.function, ref)
            )

        self.replace(arg)
