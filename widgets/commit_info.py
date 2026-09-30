from common import (
    attrof,
    mlget as _,
)
from .gui_frame import (
    GUIFrame,
)
from .gui_text import (
    READONLY,
    GUIText,
)
from .gui_toplevel import (
    GUIToplevel,
)
from .hotkey import (
    HKEntry,
)
from .scrollframe import (
    add_scrollbars_native,
)
from .var_widgets import (
    VarLabel,
)

from types import (
    FunctionType,
)
from six.moves.tkinter import (
    BOTH,
    END,
    NONE,
    StringVar,
)


def get_commit_sha(commit):
    "ID"
    return commit.hexsha

def get_commit_committer_name(commit):
    "Committer"
    return commit.committer.name

def get_commit_committer_email(commit):
    "Committer E-mail"
    return commit.committer.email

def get_commit_committed_timestamp(commit):
    "Committed Timestamp"
    return str(commit.committed_datetime)

def get_commit_author_name(commit):
    "Author"
    return commit.author.name

def get_commit_author_email(commit):
    "Author E-mail"
    return commit.author.email

def get_commit_authored_timestamp(commit):
    "Authored Timestamp"
    return str(commit.authored_datetime)


COMMIT_ATTR_GETTERS = tuple(
    f for (n, f) in globals().items() if (
            n.startswith("get_commit_")
        and isinstance(f, FunctionType)
        and f.__doc__
    )
)
COMMIT_ATTR_GETTERS = sorted(COMMIT_ATTR_GETTERS,
    key = lambda f : f.__code__.co_firstlineno
)


class CommitInfoFrame(
    GUIFrame,
    object, # for `property` (Py2)
):

    def __init__(self, *a, **kw):
        sizegrip = kw.pop("sizegrip", True)
        GUIFrame.__init__(self, *a, **kw)

        self.columnconfigure(0, weight = 0)
        self.columnconfigure(1, weight = 1)

        self._var_val_getters = vvg = []
        append = vvg.append

        for row, getter in enumerate(COMMIT_ATTR_GETTERS):
            self.rowconfigure(row, weight = 0)

            VarLabel(self,
                text = _(getter.__doc__),
            ).grid(
                row = row,
                column = 0,
                sticky = "NES",
            )
            v = StringVar(self)

            HKEntry(self,
                textvariable = v,
                state = READONLY,
            ).grid(
                row = row,
                column = 1,
                sticky = "NESW",
            )
            append((v, getter))

        row += 1
        self.rowconfigure(row, weight = 1)
        f = GUIFrame(self)
        f.grid(
            row = row,
            column = 0,
            columnspan = 2,
            sticky = "NESW",
        )
        f.rowconfigure(0, weight = 1)
        f.columnconfigure(0, weight = 1)

        self._t_commit_message = t = GUIText(f,
            state = READONLY,
            wrap = NONE,
        )
        t.grid(sticky = "NESW")
        add_scrollbars_native(f, t, sizegrip = sizegrip)

    def _read_commit(self):
        commit = self._commit
        t_cm = self._t_commit_message

        t_cm.delete("1.0", END)

        if commit is None:
            for var, __ in self._var_val_getters:
                var.set("")
            return

        for var, getter in self._var_val_getters:
            val = str(getter(commit))
            if var.get() != val:
                var.set(val)

        t_cm.insert(END, commit.message)

    _commit = None
    @property
    def commit(self):
        return self._commit

    @commit.setter
    def commit(self, commit):
        if self._commit is commit:
            return
        if commit is None:
            del self._commit
        else:
            self._commit = commit
        self._read_commit()


class CommitInfoToplevel(GUIToplevel):

    def __init__(self, *a, **kw):
        topmost = kw.pop("topmost", None)

        GUIToplevel.__init__(self, *a, **kw)

        if topmost is not None:
            self.topmost = topmost

        self.title(_("Git Commit Info"))

        self._cif = cif = CommitInfoFrame(self)
        cif.pack(fill = BOTH, expand = True)

    commit = attrof("_cif")
