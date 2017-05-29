__all__ = [
    "TaskErrorWidget",
    "TaskErrorDialog"
]

from .gui_frame import \
    GUIFrame

from .gui_dialog import \
    GUIDialog

from six.moves.tkinter import \
    VERTICAL, \
    HORIZONTAL, \
    BOTH, \
    ON, \
    END, \
    Scrollbar

from .gui_text import \
    GUIText, \
    READONLY

from traceback import \
    format_exception

from common import \
    CancelledCallee, \
    FailedCallee

class TaskErrorWidget(GUIFrame):
    def __init__(self, task, **kw):
        GUIFrame.__init__(self, **kw)

        self.grid()
        self.rowconfigure(0, weight = 1)

        # Text itself
        self.columnconfigure(0, weight = 1)
        t = GUIText(master = self, state = READONLY)
        t.grid(row = 0, column = 0, sticky = "NESW")

        # Vertical scrollbar
        self.columnconfigure(1, weight = 0)
        vsb = Scrollbar(master = self, orient = VERTICAL)
        vsb.grid(row = 0, column = 1, sticky = "NESW")

        # Horizontal scrollbar
        self.rowconfigure(1, weight = 0)
        hsb = Scrollbar(master = self, orient = HORIZONTAL)
        hsb.grid(row = 1, column = 0, sticky = "NESW")

        # Bind scrollbars and text
        t.config(yscrollcommand = vsb.set)
        vsb.config(command = t.yview)
        t.config(xscrollcommand = hsb.set)
        hsb.config(command = t.xview)

        task_traceback = []

        e = task.exception
        while isinstance(e, (CancelledCallee, FailedCallee)):
            task_traceback.append(task)

            task = e.callee
            e = task.exception

        lines = format_exception(type(e), e, task.traceback)

        lines.append("\n")
        for task in reversed(task_traceback):
            g = task.generator
            lines.append('in coroutine "%s" (%s)\n' % (
                g.__name__, type(task).__name__
            ))

        t.insert(END, "".join(lines))

class TaskErrorDialog(GUIDialog):
    def __init__(self, title, task):
        GUIDialog.__init__(self)

        self.title(title)

        TaskErrorWidget(task, master = self).pack(fill = BOTH, expand = ON)
