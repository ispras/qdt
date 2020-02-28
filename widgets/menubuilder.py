__all__ = [
    "MenuBuilder"
]

from .var_widgets import (
    VarMenu
)


class MenuBuilder(object):

    def __init__(self, toplevel, MenuClass = VarMenu):
        self.MenuClass = MenuClass
        self.toplevel = toplevel

        self.stack = []

    # `label` on first the place shortens caller code.
    def __call__(self, label = None, **kw):
        """ Remembers arguments for many menu construction functions.
Function selection is contextual, see code below.
        """

        self._flush_kw()

        kw.setdefault("label", label)
        self.prev_kw = kw
        return self

    def __enter__(self):
        stack = self.stack

        if stack:
            try:
                prev_kw = self.__dict__.pop("prev_kw")
            except KeyError:
                raise RuntimeError("Cascade menu construction arguments must"
                    " be passed by a __call__ before `with` statement"
                )
            label = prev_kw.pop("label")
            if label is None:
                raise RuntimeError("A cascade menu must have a label")

            parent = stack[-1]
            menu = self.MenuClass(parent, **prev_kw)
            parent.add_cascade(label = label, menu = menu)
        else:
            menu = self.MenuClass(self.toplevel)
            self.toplevel.config(menu = menu)

        stack.append(menu)

        return self

    def __exit__(self, *__):
        self._flush_kw()
        self.stack.pop()

    def _flush_kw(self):
        prev_kw = self.__dict__.pop("prev_kw", None)
        if prev_kw is not None:
            if prev_kw["label"] is None:
                self.stack[-1].add_separator()
            else:
                self.stack[-1].add_command(**prev_kw)

