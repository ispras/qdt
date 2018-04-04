from .branch_tree_view import (
    BranchTreeview
)
from .gui_toplevel import (
    GUIToplevel
)
from six.moves.tkinter_ttk import (
    Scrollbar
)
from common import (
    mlget as _
)

class HistoryWindow(GUIToplevel):
    def __init__(self, gui_project_history_tracker, *args, **kw):
        GUIToplevel.__init__(self, *args, **kw)

        self.guipht = gui_project_history_tracker

        self.attributes("-topmost", 1)

        self.title(_("Editing History"))

        self.grid()

        self.columnconfigure(0, weight = 1)
        self.columnconfigure(1, weight = 0)
        self.rowconfigure(0, weight = 1)
        self.rowconfigure(1, weight = 0)

        tv = self.btv = BranchTreeview(self.guipht, self)
        self.btv.grid(
            row = 0,
            column = 0,
            sticky = "NEWS"
        )

        vsb = Scrollbar(self, orient="vertical", command = tv.yview)
        vsb.grid(row = 0, column = 1, sticky = "NS")

        hsb = Scrollbar(self, orient="horizontal", command = tv.xview)
        hsb.grid(row = 1, column = 0, sticky = "EW")

        tv.configure(yscrollcommand = vsb.set, xscrollcommand = hsb.set)
