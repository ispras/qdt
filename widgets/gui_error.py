__all__ = [
    "TaskErrorWidget"
  , "TaskErrorDialog"
  , "ErrorDialog"
]

from .gui_frame import (
    GUIFrame
)
from .gui_dialog import (
    GUIDialog
)
from six.moves.tkinter import (
    END,
    NONE
)
from .gui_text import (
    GUIText,
    READONLY
)
from common import (
    mlget as _
)
from .scrollframe import (
    add_scrollbars_native
)
from .var_widgets import (
    VarLabel
)


class ErrorDialog(GUIDialog):

    def __init__(self, summary, title = None, message = None):
        GUIDialog.__init__(self)

        if title is None:
            title = _("Error")

        self.title(title)

        self.columnconfigure(0, weight = 1)

        self.rowconfigure(0, weight = 0)
        VarLabel(self, text = summary).grid(
            row = 0,
            column = 0,
            columnspan = 1 if message is None else 2,
            sticky = "NWS"
        )

        if message is not None:
            t = GUIText(self, state = READONLY, wrap = NONE)

            self.rowconfigure(1, weight = 1)
            t.grid(row = 1, column = 0, sticky = "NESW")

            add_scrollbars_native(self, t, row = 1, sizegrip = True)

            t.insert(END, message)


class TaskErrorWidget(GUIFrame):
    def __init__(self, task, **kw):
        GUIFrame.__init__(self, **kw)

        self.grid()
        self.rowconfigure(0, weight = 1)

        # Text itself
        self.columnconfigure(0, weight = 1)
        t = GUIText(master = self, state = READONLY, wrap = NONE)
        t.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(self, t, sizegrip = True)

        t.insert(END, "".join(task.traceback_lines))


class TaskErrorDialog(ErrorDialog):

    def __init__(self, task, summary = None, title = None):
        if summary is None:
            summary = _("%s - failed") % task.description

        message = "".join(task.traceback_lines)

        ErrorDialog.__init__(self, summary, title = title, message = message)
