__all__ = [
    "FormatedStringChangindException"
  , "FormatVar"
  , "as_variable"
]

from six.moves.tkinter import (
    Variable as TkVariable,
    StringVar
)
from .variable import (
    Variable
)


variables = (Variable, TkVariable)


def as_variable(*args):
    """ Decorator for a callable. It transforms the callable to a `Variable`
which value is evaluated by the callable using values of `args`. The value
will be automatically recomputed when one of `args` changed. Changes of values
of non-`Variable` `args` cannot be accounted.
    """

    def create_variable(f):
        var = Variable()

        def _on_arg_changed(*_):
            "When an arg changed, this function updates var using f"
            vals = []
            for a in args:
                if isinstance(a, variables):
                    vals.append(a.get())
                else:
                    vals.append(a)

            var.set(f(*vals))

        for a in args:
            if isinstance(a, variables):
                a.trace_variable("w", _on_arg_changed)

        # initial computing
        _on_arg_changed()

        # TODO: a lazy computation, during `get` method
        return var

    return create_variable


class FormatedStringChangindException(TypeError):
    pass


def forbid_set(self, value):
    # External formated string changing is forbidden.
    raise FormatedStringChangindException()

# The class just implements % (__mod__) operator for StringVar
class FormatVar(Variable):
    def __mod__(self, args):

        if not isinstance(args, tuple):
            args = (args,)

        @as_variable(self, *args)
        def do_format(fmt, *args):
            return fmt % args

        # Wrapping do_format in `StringVar` is required because
        # `Variable` instance cannot be used with Tk.
        # TODO: move that mechanics elsewhere making `FormatVar` Tk
        # independent.

        # Initial setting
        ret = StringVar(value = do_format.get())

        # Auto update
        do_format.trace_variable("w",
            lambda : StringVar.set(ret, do_format.get())
        )

        ret.set = forbid_set

        return ret
