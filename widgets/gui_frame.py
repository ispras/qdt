__all__ = [
    "GUIFrame"
]

from six.moves.tkinter import (
    Frame
)
from .tk_unbind import (
    unbind
)

class GUIFrame(Frame):
    unbind = unbind

    def __init__(self, *args, **kwargs):
        Frame.__init__(self, *args, **kwargs)

    def enqueue(self, co_task):
        "Its toplevel must be GUITk."
        self.winfo_toplevel().enqueue(co_task)

    def cancel_task(self, co_task):
        "Its toplevel must be GUITk."
        self.winfo_toplevel().cancel_task(co_task)
