__all__ = [
    "TaskErrorWidget"
  , "TaskErrorDialog"
]

from .gui_frame import (
    GUIFrame
)
from .gui_dialog import (
    GUIDialog
)
from six.moves.tkinter import (
    BOTH,
    ON,
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

class TaskErrorDialog(GUIDialog):
    def __init__(self, task):
        GUIDialog.__init__(self)

        self.title(_("%s - failed") % task.description)

        TaskErrorWidget(task, master = self).pack(fill = BOTH, expand = ON)
