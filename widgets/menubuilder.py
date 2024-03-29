__all__ = [
    "MenuBuilder"
]

from .var_widgets import (
    VarMenu,
)


class MenuBuilder(object):

    def __init__(self, toplevel, MenuClass = VarMenu, assign = True, **root_kw):
        """
@param toplevel:
    a first positional argument of MenuClass.
    It must be a Toplevel/Tk if assign is True.
@param MenuClass:
    callable, a factory of menus
@param assign:
    root menu will be assigned to `toplevel`
@param root_kw:
    all unknown keyword args are used as kw for MenuClass
        """
        self.MenuClass = MenuClass
        self.toplevel = toplevel
        self.assign = assign
        self.root_kw = root_kw

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
            menu = prev_kw.get("menu")
            if menu is None:
                menu = self.MenuClass(parent, **prev_kw)
            # else: # ignore the rest of `prev_kw`
            parent.add_cascade(label = label, menu = menu)
        else:
            menu = self.MenuClass(self.toplevel, **self.root_kw)
            if self.assign:
                self.toplevel.config(menu = menu)

        stack.append(menu)

        return self

    @property
    def menu(self):
        return self.stack[-1]

    def __exit__(self, *__):
        self._flush_kw()
        self.stack.pop()

    def _flush_kw(self):
        prev_kw = self.__dict__.pop("prev_kw", None)
        if prev_kw is not None:
            parent = self.stack[-1]
            if prev_kw["label"] is None:
                parent.add_separator()
            else:
                if "variable" in prev_kw:
                    parent.add_checkbutton(**prev_kw)
                else:
                    parent.add_command(**prev_kw)

