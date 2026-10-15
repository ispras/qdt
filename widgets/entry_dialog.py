__all__ = [
    "EntryDialog"
]

from common import (
    mlget as _,
)

from .gui_dialog import (
    GUIDialog,
)
from .hotkey import (
    HKEntry,
)
from .tk_after import (
    tk_delayed,
)
from .var_widgets import (
    VarButton,
)

from six.moves.tkinter import (
    END,
    StringVar,
)

class EntryDialog(GUIDialog):

    def __init__(self, *a, **kw):
        title = kw.pop("title", None)
        value = kw.pop("value", None)
        GUIDialog.__init__(self, *a, **kw)

        if title:
            self.title(title)

        self.rowconfigure(0, weight = 1)
        self.rowconfigure(1, weight = 0)
        self.columnconfigure(0, weight = 1)
        self.columnconfigure(1, weight = 1)

        v = self._var = StringVar()
        e = self._entry = HKEntry(self, textvariable = v)
        e.grid(row = 0, column = 0, columnspan = 2, sticky = "NESW")

        e.focus_set()

        if value is None:
            v.set("")
        else:
            v.set(value)

        VarButton(self, text = _(u"Ok"), command = self._on_ok).grid(
            row = 1, column = 0, sticky = "W"
        )
        VarButton(self, text = _(u"Cancel"), command = self._on_cancel).grid(
            row = 1, column = 1, sticky = "E"
        )

        self.bind("<Return>", self._on_ok, "+")
        self.bind("<Escape>", self._on_cancel, "+")
        self.bind("<Destroy>", self._on_destroy, "+")

        self._delayed_init = 10

    @tk_delayed
    def _delayed_init(self):
        e = self._entry

        e.selection_range(0, END)
        e.icursor(END)

    def _on_cancel(self, __ = None):
        self.destroy()

    def _on_ok(self, __ = None):
        res = self._var.get()
        if res:
            self._result = res
        self.destroy()

    def _on_destroy(self, __):
        del self._delayed_init
