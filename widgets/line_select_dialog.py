__all__ = [
    "LineSelectDialog"
]

from .auto_var_treeview import (
    AutoVarTreeview,
)
from common import (
    mlget as _,
)
from .gui_dialog import (
    GUIDialog,
)
from .gui_frame import (
    GUIFrame,
)
from .scrollframe import (
    add_scrollbars_native,
)
from .var_widgets import (
    VarButton,
)

from six.moves.tkinter import (
    BROWSE,
    DISABLED,
    END,
    LEFT,
    NORMAL,
    RIGHT,
)


class LineSelectDialog(GUIDialog):
    "Allows a user to select one of options presented by `lines`."

    def __init__(self, *a, **kw):
        # properties
        self._lines = None

        lines = kw.pop("lines", None)
        GUIDialog.__init__(self, *a, **kw)

        self._tv = tv = AutoVarTreeview(self,
            selectmode = BROWSE,
        )

        tv.bind("<<TreeviewSelect>>", self._on_tv_select, "+")
        tv.bind("<Double-Button-1>", self._on_tv_double_b1, "+")

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)

        tv.grid(row = 0, column = 0, columnspan = 2, sticky = "NESW")

        add_scrollbars_native(self, tv)

        fr = GUIFrame(self)
        fr.grid(row = 2, column = 0, columnspan = 2, sticky = "NESW")

        self._bt_ok = bt = VarButton(fr, text = _("OK"), command = self._on_ok)
        bt.pack(side = LEFT)
        bt.config(state = DISABLED)

        VarButton(fr,
            text = _("Cancel"),
            command = self.destroy,
        ).pack(
            side = RIGHT
        )

        self.lines = lines

    @property
    def lines(self):
        return self._lines

    @lines.setter
    def lines(self, lines):
        if self._lines:
            self._cleanup()

        self._lines = lines
        if lines:
            self._fill()

    def _fill(self):
        tv = self._tv
        insert = tv.insert
        for l in self._lines:
            insert("", END, text = l)
        tv.adjust_widths()

    def _cleanup(self):
        self._bt_ok.config(state = DISABLED)
        self._tv.delete(*self._tv.get_children())

    def _on_ok(self):
        tv = self._tv

        self._result = tv.index(tv.selection()[0])

        self.destroy()

    def _on_tv_double_b1(self, __):
        self._on_ok()

    def _on_tv_select(self, __):
        if self._tv.selection():
            state = NORMAL
        else:
            state = DISABLED
        self._bt_ok.config(state = state)
