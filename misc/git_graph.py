from argparse import (
    ArgumentParser
)
from six.moves.tkinter import (
    ALL,
    BOTH
)
from git import (
    Repo
)
from common import (
    ee,
    mlget as _
)
from widgets import (
    add_scrollbars_native,
    CanvasDnD,
    GUIFrame,
    GUITk
)
from libe.common.events import (
    dismiss,
    listen,
)
from libe.git.macrograph import (
    GitMacrograph,
    GitMgEdge,
    GitMgNode,
)
from libe.graph.dynamic_placer import (
    DynamicGraphPlacer2D,
)


# Set this env. var. to output macrograph to file in Graphviz format.
DOT_FILE_NAME = ee("GIT_GRAPH_DOT_FILE_NAME", "None")


class GGVWidget(GUIFrame):
    """Git Graph View Widget
    """

    def __init__(self, *a, **kw):
        sizegrip = kw.pop("sizegrip", False)

        GUIFrame.__init__(self, *a, **kw)

        self._repo_path = None
        self._co_visualize = None

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)
        self._cnv = cnv = CanvasDnD(self)
        cnv.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(self, cnv, sizegrip = sizegrip)

        cnv.bind("<<DnDMoved>>", lambda __: cnv.update_scroll_region(), "+")

    @property
    def repo_path(self):
        return self._repo_path

    @repo_path.setter
    def repo_path(self, p):
        if p == self._repo_path:
            return
        self._repo_path = p

        co = self._co_visualize
        if co is not None:
            self._co_visualize = None
            self.cancel_task(co)
            self._cnv.delete(ALL)
            self._cnv.update_scroll_region()
            del self._o2iid
            del self._dgp
            dismiss(self._on_node_placed)
            dismiss(self._on_edge_placed)

        if p is None:
            return

        self._repo = Repo(p)

        self._co_visualize = co = self.co_visualize()
        self.enqueue(co)

    def co_visualize(self):
        self._o2iid = {}

        self._dgp = dgp = DynamicGraphPlacer2D()

        listen(dgp, "node", self._on_node_placed)
        listen(dgp, "edge", self._on_edge_placed)

        mg = GitMacrograph(self._repo)

        mg.watch_node(self._on_mg_node)
        mg.watch_edge(self._on_mg_edge)

        print("Building GitMacrograph")

        for i in mg.co_build():
            while dgp.has_work:
                yield dgp.co_place()
            yield i

        print("Done")

        tags_n = len(mg._edges)
        for c in mg._edges:
            if c.is_merge or c.is_fork or c.is_leaf or c.is_root:
                tags_n -= 1

        print(
            "total: ", len(mg._edges),
            " tags: ",  tags_n,
            " other: ", len(mg._edges) - tags_n,
        )

        if DOT_FILE_NAME is not None:
            yield True
            print("Writing Graphviz file: " + DOT_FILE_NAME)
            src = mg.gen_gv().source
            yield True
            with open(DOT_FILE_NAME, "w") as f:
                f.write(src)
            print("Done")

    def _on_mg_node(self, mg, mn):
        self._dgp.add_node(mn)

    def _on_mg_edge(self, mg, e, split):
        p = self._dgp

        if split is not None:
            # re-create with new edges
            p.remove_node(split)
            if split:
                p.add_node(split)

        if e:
            p.add_node(e)
            p.add_edge(e._descendant, e)
            p.add_edge(e, e._ancestor)
        else:
            # no commits between macronodes
            p.add_edge(e._descendant, e._ancestor)

        if split is not None:
            if split:
                p.add_edge(split._descendant, split)
                p.add_edge(split, split._ancestor)
            else:
                p.add_edge(split._descendant, split._ancestor)

    def _on_node_placed(self, n):
        cnv = self._cnv
        dgp = self._dgp
        o2iid = self._o2iid

        # logical coordinates
        lxy = dgp.node_coords(n)

        try:
            (riid, tiid) = o2iid[n]
        except KeyError:
            if lxy is None:
                # removed
                return
            riid = cnv.create_rectangle(0, 0, 0, 0, fill = "white")
            tiid = cnv.create_text(0, 0, text = "")
            o2iid[n] = (riid, tiid)
        else:
            if lxy is None:
                # removed
                cnv.delete(riid, tiid)
                del o2iid[n]

                cnv.update_scroll_region()
                return

        if isinstance(n, GitMgNode):
            cnv.itemconfig(tiid, text = n.pretty)
        elif isinstance(n, GitMgEdge):
            l = len(n)
            # assert l  # just print a warning instead
            if not l:
                print("Error: len(GitMgEdge) == 0 should not be placed")
            cnv.itemconfig(tiid, text = str(l))
        else:
            raise RuntimeError(type(n))

        lx, ly = lxy

        # pixel coordinates
        px = 100 * lx
        py = 40 * ly

        cnv.coords(tiid, px, py)

        l, t, r, b = cnv.bbox(tiid)
        w_2 = ((r - l) / 2 + 3)
        h_2 = ((b - t) / 2 + 3)

        cnv.coords(riid,
            px - w_2,
            py - h_2,
            px + w_2,
            py + h_2,
        )

        cnv.update_scroll_region()

    def _on_edge_placed(self, *ab):
        cnv = self._cnv
        dgp = self._dgp
        o2iid = self._o2iid

        try:
            iid = o2iid[ab]
        except KeyError:
            iid = cnv.create_line(0, 0, 0, 0,
                smooth = True,
            )
            o2iid[ab] = iid
            cnv.lower(iid)

        coords = []
        coord = coords.append

        for lx, ly in dgp.iter_edge_coords(*ab):
            px = 100 * lx
            py = 40 * ly
            coord(px)
            coord(py)

        if coords:
            cnv.coords(iid, coords)
        else:
            # removed
            del o2iid[ab]
            cnv.delete(iid)

        cnv.update_scroll_region()


class GGVWindow(GUITk):

    def __init__(self, repo):
        GUITk.__init__(self)
        self.title(_("Git Graph Viewer"))

        w = GGVWidget(self, sizegrip = True)
        w.pack(fill = BOTH, expand = True)

        # print("repo = " + repo)
        w.repo_path = repo


def main():
    ap = ArgumentParser(description = "Git Graph Viewer")
    ap.add_argument("repo")

    args = ap.parse_args()

    root = GGVWindow(**vars(args))
    root.geometry("900x900")
    root.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
