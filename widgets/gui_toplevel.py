__all__ = [
    "GUIToplevel"
]

from .var_widgets import (
    VarToplevel
)
from .logo import (
    set_logo
)


# `object` superclass is required for `property` decorator.
class GUIToplevel(VarToplevel, object):

    def __init__(self, *args, **kw):
        VarToplevel.__init__(self, *args, **kw)

        set_logo(self)

    # Makes settings window always on top.
    # Is there more pythonic interface?
    # http://effbot.org/tkinterbook/wm.htm#Tkinter.Wm.attributes-method
    @property
    def topmost(self):
        return self.attributes("-topmost")

    @topmost.setter
    def topmost(self, val):
        self.attributes("-topmost", val)

    @property
    def hk(self):
        return self.master.hk

    def enqueue(self, co_task):
        "Its master must be GUITk."
        self.master.enqueue(co_task)

    def cancel_task(self, co_task):
        "Its master must be GUITk."
        self.master.cancel_task(co_task)
