__all__ = [
    "GUIFrame"
]

from .tk_unbind import (
    unbind,
)

from six.moves.tkinter import (
    Frame,
)


class GUIFrame(Frame):
    unbind = unbind

    def enqueue(self, co_task):
        "Its toplevel must be GUITk."
        self.winfo_toplevel().enqueue(co_task)

    def cancel_task(self, co_task):
        "Its toplevel must be GUITk."
        self.winfo_toplevel().cancel_task(co_task)
