__all__ = [
    "GUIToplevel"
]

from .logo import (
    set_logo,
)
from .var_widgets import (
    VarToplevel,
)


# `object` superclass is required for `property` decorator.
class GUIToplevel(VarToplevel, object):

    def __init__(self, *args, **kw):
        VarToplevel.__init__(self, *args, **kw)

        set_logo(self)

    # Makes this window always on top.
    # Is there more pythonic interface?
    # https://dafarry.github.io/tkinterbook/wm.htm#Tkinter.Wm.attributes-method
    @property
    def topmost(self):
        return self.attributes("-topmost")

    @topmost.setter
    def topmost(self, val):
        self.attributes("-topmost", val)

    @property
    def hk(self):
        # master is expected to be GUITk or GUIToplevel
        return self.master.hk

    def enqueue(self, co_task):
        # master is expected to be GUITk or GUIToplevel
        self.master.enqueue(co_task)

    def cancel_task(self, co_task):
        # master is expected to be GUITk or GUIToplevel
        self.master.cancel_task(co_task)
