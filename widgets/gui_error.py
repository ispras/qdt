__all__ = [
    "TaskErrorDialog"
  , "ErrorDialog"
]

from .gui_dialog import (
    GUIDialog
)
from six.moves.tkinter import (
    END,
    NONE
)
from six.moves.tkinter_ttk import (
    Sizegrip
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
    VarButton,
    VarLabel
)
from sys import (
    stderr
)


class ErrorDialog(GUIDialog):

    def __init__(self, summary, title = None, message = None):
        GUIDialog.__init__(self)

        if title is None:
            title = _("Error")

        self._title = title
        self._summary = summary
        self._message = message

        self.title(title)

        self.columnconfigure(0, weight = 1)

        row = 0

        self.rowconfigure(row, weight = 0)
        VarLabel(self, text = summary).grid(
            row = row,
            column = 0,
            columnspan = 1 if message is None else 2,
            sticky = "NWS"
        )
        row += 1

        if message is not None:
            t = GUIText(self, state = READONLY, wrap = NONE)

            self.rowconfigure(row, weight = 1)
            t.grid(row = row, column = 0, sticky = "NESW")

            add_scrollbars_native(self, t, row = row, sizegrip = False)

            row += 2

            t.insert(END, message)

        self.rowconfigure(row, weight = 0)
        VarButton(self,
            text = _("Print to stderr"),
            command = self._on_print_to_stderr
        ).grid(
            row = row,
            column = 0,
            sticky = "NWS"
        )

        Sizegrip(self).grid(
            row = row,
            column = 1,
            sticky = "SE"
        )

        row += 1

    def _on_print_to_stderr(self):
        stderr.write("%s\n%s\n%s\n" % (
            self._title.get(),
            self._summary.get(),
            self._message
        ))


class TaskErrorDialog(ErrorDialog):

    def __init__(self, task, summary = None, title = None):
        if summary is None:
            summary = _("%s - failed") % task.description

        message = "".join(task.traceback_lines)

        ErrorDialog.__init__(self, summary, title = title, message = message)
