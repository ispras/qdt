__all__ = [
    "GitVerSelWidget"
  , "GitVerSelDialog"
]


from six.moves.tkinter import (
    StringVar
)
from six.moves.tkinter_ttk import (
    Combobox
)
from common import (
    mlget as _
)
from .gui_dialog import (
    GUIDialog
)
from .gui_frame import (
    GUIFrame
)
from .var_widgets import (
    VarButton
)


class GitVerSelWidget(GUIFrame):

    def __init__(self, master, repo, *a, **kw):
        GUIFrame.__init__(self, master, *a, **kw)

        if repo is None:
            refname = ""
            refs = []
        else:
            # auto select HEAD as ref
            try:
                refname = repo.head.ref.name
            except TypeError:
                refname = repo.head.commit.hexsha

            refs = [r.name for r in repo.references]

        selected = StringVar()
        cb = Combobox(self,
            width = 41, # To fit 40 hex digits of git SHA1
            values = refs,
            textvariable = selected
        )
        cb.pack(side = "top", fill = "x", expand = True)

        selected.set(refname)

        self.selected = selected


class GitVerSelDialog(GUIDialog):

    def __init__(self, master, repo, *a, **kw):
        GUIDialog.__init__(self, master, *a, **kw)

        self.title(_("Select Git version"))

        w = GitVerSelWidget(self, repo)
        w.pack(fill = "both", expand = True)

        VarButton(self,
            text = _("Select"),
            command = self._on_select
        ).pack(side = "bottom")

        self.w = w

        # select on Enter
        self.bind_all("<Return>", self._on_enter, "+")

    def _on_enter(self, *__):
        self._on_select()

    def _on_select(self):
        res = self.w.selected.get()
        if res:
            self._result = res
        self.destroy()
