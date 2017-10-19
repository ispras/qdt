from six.moves.tkinter import (
    Variable as TkVariable,
    StringVar
)
from .variable import Variable

variables = (Variable, TkVariable)

class FormatedStringChangindException(BaseException):
    pass

# The class just implements % (__mod__) operator for StringVar
class FormatVar(Variable):
    def __mod__(self, args):

        if not isinstance(args, tuple):
            args = (args,)

        return FormatedStringVar(
            fmt = self,
            fmt_args = args
        )

class FormatedStringVar(StringVar):
    def __init__(self, fmt, fmt_args):
        self.fmt = fmt
        self.fmt_args = fmt_args

        for a in ( fmt, ) + fmt_args:
            if isinstance(a, variables):
                a.trace_variable("w", self.__on_fmt_arg_changed__)

        """ FormatedStringVar.set method forbids setting of self value. But
Variable.__init__ calls self.set which is normally FormatedStringVar.set. It
temporally replaces self.set with nope lambda to bypass this.
        """
        tmp = self.set
        self.set = lambda x: None

        StringVar.__init__(self)

        self.set = tmp

        StringVar.set(self, self.__gen_string__())

    @staticmethod
    def __arg_get__(arg):
        if isinstance(arg, variables):
            return arg.get()
        else:
            return arg

    def __gen_string__(self):
        fmt = self.fmt

        if isinstance(fmt, variables):
            fmt = fmt.get()

        args = [ FormatedStringVar.__arg_get__(arg) for arg in self.fmt_args ]

        return fmt % tuple(args)

    def __on_fmt_arg_changed__(self, *args, **hw):
        # Format or argument is changed - update value
        StringVar.set(self, self.__gen_string__())

    def set(self, value):
        # External formated string changing is forbidden.
        raise FormatedStringChangindException()

# Test
if __name__ == "__main__":
    # at least one Tk instance should exist
    from six.moves.tkinter import Tk
    root = Tk()

    fmt = FormatVar(value = "Text example is '%s'")
    text = StringVar(value = "[ a text will be here ]")
    res = fmt % text

    def on_w(*args):
        print(res.get())

    res.trace_variable("w", on_w)

    for action in (
        on_w,
        lambda : text.set("A text"),
        lambda : fmt.set("'%s' is the text example.")
    ):
        action()
