__all__ = [
    "GitVerSelWidget"
  , "GitVerSelDialog"
]

from common import (
    mlget as _,
)
from .gui_dialog import (
    GUIDialog,
)
from .gui_frame import (
    GUIFrame,
)
from .hotkey import (
    HKCombobox,
)
from .var_widgets import (
    VarButton,
)

from collections import (
    defaultdict,
)
from six.moves.tkinter import (
    StringVar,
)


class ShaInfo(object):

    def __init__(self):
        self.name2origins = defaultdict(list)

    def account_ref(self, ref):
        refpath = tuple(ref.path.split("/"))
        if refpath[1] == "tags":
            disp_name = "T: " #ag
        else:
            disp_name = "B: " #ranch
        disp_name += refpath[-1]
        origin = refpath[2:-1]
        if origin:
            # remote
            self.name2origins[disp_name].append("/".join(origin))
        else:
            # local, only trigger entry instantiation
            self.name2origins[disp_name]

    def iter_values(self):
        for disp_name, origins in self.name2origins.items():
            value = disp_name
            if origins:
                value += " (" + ", ".join(origins) + ")"
            yield value


class GitVerSelWidget(GUIFrame):

    def __init__(self, master, repo, *a, **kw):
        GUIFrame.__init__(self, master, *a, **kw)

        self.hexsha2refs = hexsha2refs = defaultdict(ShaInfo)
        self.value2hexsha = value2hexsha = {}

        if repo is None:
            refname = ""
            values = []
        else:

            for ref in repo.references:
                shainfo = hexsha2refs[ref.commit.hexsha]
                shainfo.account_ref(ref)

            for hexsha, shainfo in hexsha2refs.items():
                for value in shainfo.iter_values():
                    value2hexsha[value] = hexsha

            cur_hexsha = repo.head.commit.hexsha
            if cur_hexsha not in hexsha2refs:
                value = "C: " + repr(cur_hexsha)[1:-1]
                value2hexsha[value] = cur_hexsha
                # auto select HEAD as ref
                refname = value
            else:
                refname = next(hexsha2refs[cur_hexsha].iter_values())

            values = list(value2hexsha)
            values.sort(key = lambda s: s.lower())

        self.selected = selected = StringVar(self)
        self.ignore_selected_var_writes = False
        selected.trace_variable("w", self.on_selected_var_write)

        self.cbvar = cbvar = StringVar(self)
        cbvar.trace_variable("w", self.on_cb_var_write)

        cb = HKCombobox(self,
            width = 41, # To fit 40 hex digits of git SHA1
            values = values,
            textvariable = cbvar,
        )
        cb.pack(side = "top", fill = "x", expand = True)

        cbvar.set(refname)

    def on_cb_var_write(self, *__):
        value = self.cbvar.get()
        hexsha = self.value2hexsha.get(value)
        if hexsha:
            translated = hexsha
        else:
            # Custom user input must be a valid Git reference.
            translated = value

        self.ignore_selected_var_writes = True
        self.selected.set(translated)
        self.ignore_selected_var_writes = False

    def on_selected_var_write(self, *__):
        if self.ignore_selected_var_writes:
            return
        raise NotImplementedError("find out corresponding entry")


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
