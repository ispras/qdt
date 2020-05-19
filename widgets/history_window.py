__all__ = [
    "HistoryWindow"
]

from .branch_tree_view import (
    BranchTreeview
)
from .gui_toplevel import (
    GUIToplevel
)
from .scrollframe import (
    add_scrollbars_native
)
from common import (
    mlget as _
)


class HistoryWindow(GUIToplevel):

    def __init__(self, gui_project_history_tracker, *args, **kw):
        GUIToplevel.__init__(self, *args, **kw)

        self.guipht = gui_project_history_tracker

        self.topmost = True

        self.title(_("Editing History"))

        self.grid()

        self.columnconfigure(0, weight = 1)
        self.rowconfigure(0, weight = 1)

        tv = self.btv = BranchTreeview(self.guipht, self)
        self.btv.grid(
            row = 0,
            column = 0,
            sticky = "NEWS"
        )

        add_scrollbars_native(self, tv, sizegrip = True)
