__all__ = [
    "GitRefTree"
      , "GitRefFrame"
]

from .auto_var_treeview import (
    AutoVarTreeview,
)
from .git_ref_selector import (
    ShaInfo,
)
from .gui_frame import (
    GUIFrame,
)
from .scrollframe import (
    add_scrollbars_native,
)
from .tk_after import (
    tk_delayed,
)

from common import (
    attrof,
    kw_extract,
    mlget as _,
    ready,
)

from collections import (
    defaultdict,
)
from six.moves.tkinter import (
    END,
)


def GIT_REF_ORDER_NAME(info):
    return sorted(info.name2origins)


class GitRefTree(AutoVarTreeview):

    def __init__(self, master,
        repo = None,
        sort_order = None,
        sha_width = None,
        **kw
    ):
        columns = [
            "r",
        ]
        super(GitRefTree, self).__init__(master,
            columns = columns,
            **kw
        )

        self.heading("#0",
            text = _("SHA")
        )
        self.heading("r",
            text = _("Name")
        )

        self._no_loc_name = _("[no local name]")

        if repo is not None:
            self.repo = repo
        if sort_order is None:
            sort_order = GIT_REF_ORDER_NAME
        self.sort_order = sort_order
        if sha_width is None:
            sha_width = 8
        self.sha_width = sha_width

    @ready
    def _tree_content(self, ready):
        if not ready:
            c = self.get_children("")
            if c:
                self.delete(*c)
            del self._iid2info
            del self._shainfos
            return

        self._shainfos = shainfos = defaultdict(ShaInfo)
        repo = self._repo
        if repo is not None:
            for ref in repo.references:
                sha = ref.commit.hexsha
                info = shainfos[sha]
                info.sha = sha
                info.account_ref(ref)

        # finalize, prepare for sorting
        for info in shainfos.values():
            n2o = info.name2origins
            for n, os in tuple(n2o.items()):
                n2o[n] = tuple(sorted(os))

        infos = sorted(shainfos.values(),
            key = self._sort_order,
        )

        self._iid2info = iid2info = {}
        insert = self.insert
        nln = self._no_loc_name
        sha_width = self._sha_width
        for info in infos:
            iid = insert("", END,
                text = info.sha[:sha_width],
                open = True,
                values = (
                    info.local_name or nln,
                ),
            )
            iid2info[iid] = info
            for n, os in sorted(info.name2origins.items()):
                for o in os:
                    oiid = insert(iid, END,
                        open = True,
                        text = o,
                        values = (
                            n,
                        ),
                    )
                    iid2info[oiid] = info

        self._do_adjust_widths = 100

    sort_order = _tree_content.bit()
    repo = _tree_content.bit()
    sha_width = _tree_content.bit()

    @tk_delayed
    def _do_adjust_widths(self):
        self.adjust_widths(hidden = True)


class GitRefFrame(GUIFrame, object):

    def __init__(self, *a, **kw):
        sizegrip = kw.pop("sizegrip", False)
        grtkw = kw_extract(kw, GitRefTree)
        super(GitRefFrame, self).__init__(*a, **kw)
        self._tv = tv = GitRefTree(self, **grtkw)
        add_scrollbars_native(self, tv, 0, 0,
            sizegrip = sizegrip,
            insert_weight = 1,
        )

    repo = attrof("_tv")
    sort_order = attrof("_tv")
    sha_width = attrof("_tv")
