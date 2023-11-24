from common import (
    bidict,
    ee,
    mlget as _,
    REFS_ORDER_RECENT_FIRST,
)
from widgets import (
    add_scrollbars_native,
    CanvasDnD,
    GUIFrame,
    GUITk,
    MenuBuilder,
    VarToplevel,
    VarTreeview,
)
from libe.common.events import (
    dismiss,
    listen,
)
from libe.common.grid import (
    Grid,
)
from libe.common.gridrect import (
    GridRect,
)
from libe.git.macrograph import (
    GitMacrograph,
    GitMgEdge,
    GitMgNode,
)
from libe.graph.dynamic_placer import (
    DynamicGraphPlacer2D,
)
from libe.widgets.tk.hide_show_binding import (
    HideShowBinding,
)

from argparse import (
    ArgumentParser,
)
from collections import (
    deque,
)
from git import (
    Repo,
)
from itertools import (
    count,
)
from six.moves.tkinter import (
    ALL,
    BOTH,
    BooleanVar,
    BROWSE,
)


# Set this env. var. to output macrograph to file in Graphviz format.
DOT_FILE_NAME = ee("GIT_GRAPH_DOT_FILE_NAME", "None")


class _CanvasItem:

    _size = None
    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, size):
        if self._size == size:
            return
        self._size = size
        self._invalidate()

    _coords = None
    @property
    def coords(self):
        return self._coords

    @coords.setter
    def coords(self, coords):
        if self._coords == coords:
            return
        self._coords = coords
        self._invalidate()

    _valid = True
    def _invalidate(self):
        if self._valid:
            self._valid = False

            # Note, thi's GGVWidget specific.
            self._c.master._jobs.append(self._update_canvas_coords)

    def _update_canvas_coords(self):
        del self._valid
        self.__update_canvas_coords__()


class TextGridBox(GridRect, _CanvasItem):

    def __init__(self, canvas):
        self._c = canvas
        self._riid = canvas.create_rectangle(0, 0, 0, 0)
        self._tiid = canvas.create_text(0, 0, text = "")

        super(TextGridBox, self).__init__((0, 0))


    def iter_iids(self):
        yield self._riid
        yield self._tiid

    def delete(self):
        self._c.delete(*self.iter_iids())

    def set_text(self, text):
        c = self._c
        tiid = self._tiid
        c.itemconfig(tiid, text = text)
        l, t, r, b = c.bbox(tiid)
        self.size = (r - l + 12, b - t + 12)

    def set_styles(self, text_style, rect_style):
        icfg = self._c.itemconfig
        icfg(self._tiid, **text_style)
        icfg(self._riid, **rect_style)

    def __update_canvas_coords__(self):
        gcoords = self._gcoords
        if gcoords is None:
            return

        c = self._c
        riid = self._riid
        tiid = self._tiid
        g = self._g

        x, y = self._coords

        i, j = gcoords
        x1, y1 = g((i + 1, j + 1))

        x = (x + x1) / 2
        y = (y + y1) / 2

        w, h = self._size
        w_2 = w / 2
        h_2 = h / 2

        c.coords(tiid, x, y)

        c.coords(riid,
            x - w_2 + 3,
            y - h_2 + 3,
            x + w_2 - 3,
            y + h_2 - 3,
        )

        c.extend_scroll_region()


class _GridLinePoint(GridRect, _CanvasItem):

    def __init__(self, line, coordi, size = 10, **kw):
        self._l = line
        self._ci = coordi

        super(_GridLinePoint, self).__init__((size, size), **kw)

    @property
    def _c(self):
        return self._l._c

    def __update_canvas_coords__(self):
        gcoords = self._gcoords
        if gcoords is None:
            return

        x, y = self._coords
        i, j = gcoords
        x1, y1 = self._g((i + 1, j + 1))

        x = (x + x1) / 2
        y = (y + y1) / 2

        c = self._c
        iid = self._l._liid

        ci = self._ci
        lcoords = c.coords(iid)
        lcoords[ci : ci + 2] = (x, y)
        c.coords(iid, *lcoords)

        c.extend_scroll_region()


class GridLine(object):

    def __init__(self, canvas, gcoords):
        self._c = canvas
        gcoords_len = len(gcoords)
        self._liid = liid = canvas.create_line(
            *list(range(gcoords_len)),
            **dict(smooth = True)
        )
        canvas.lower(liid)
        points = []
        point = points.append
        gciter = iter(gcoords)
        for coordi, i in zip(count(0, 2), gciter):
            j = next(gciter)
            point(_GridLinePoint(self, coordi, gcoords = (i, j)))
        self._points = points

    def set_gcoords(self, gcoords):
        gciter = iter(gcoords)
        for p in self._points:
            p.gcoords = (next(gciter), next(gciter))

    _g = None
    @property
    def g(self):
        return self._g

    @g.setter
    def g(self, g):
        if g is self._g:
            return
        if g is None:
            del self._g
        else:
            self._g = g
        for p in self._points:
            p.g = g

    def remove(self):
        self.g = None
        self._c.delete(self._liid)


class GGVWidget(GUIFrame):
    """Git Graph View Widget
    """

    EDGE_RECT_NORMAL = dict(
        tags = "e",
        fill = "white",
    )
    EDGE_TEXT_NORMAL = dict(
        tags = "e",
        fill = "black",
    )
    EDGE_RECT_SELECTED = dict(
        tags = "e",
        fill = "black",
    )
    EDGE_TEXT_SELECTED = dict(
        tags = "e",
        fill = "white"
    )

    NODE_RECT_NORMAL = dict(EDGE_RECT_NORMAL)
    NODE_RECT_NORMAL["tags"] = "n"
    NODE_TEXT_NORMAL = dict(EDGE_TEXT_NORMAL)
    NODE_TEXT_NORMAL["tags"] = "n"
    NODE_RECT_SELECTED = dict(EDGE_RECT_SELECTED)
    NODE_RECT_SELECTED["tags"] = "n"
    NODE_TEXT_SELECTED = dict(EDGE_TEXT_SELECTED)
    NODE_TEXT_SELECTED["tags"] = "n"

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

        cnv.bind("<<DnDMoved>>", lambda __: cnv.extend_scroll_region(), "+")
        cnv.tag_bind("e", "<Button-1>", self._on_item_b1, "+")
        cnv.tag_bind("n", "<Button-1>", self._on_item_b1, "+")

        self._edge = None
        self._node = None

    @property
    def edge(self):
        return self._edge

    @edge.setter
    def edge(self, edge):
        cur_edge = self._edge
        if edge is cur_edge:
            return

        if cur_edge is not None:
            b = self._o2b[cur_edge]
            b.set_styles(self.EDGE_TEXT_NORMAL, self.EDGE_RECT_NORMAL)

        if edge is not None:
            b = self._o2b[edge]
            b.set_styles(self.EDGE_TEXT_SELECTED, self.EDGE_RECT_SELECTED)

        self._edge = edge

        self.event_generate("<<Edge>>")

    @property
    def node(self):
        return self._node

    @node.setter
    def node(self, node):
        cur_node = self._node
        if node is cur_node:
            return

        if cur_node is not None:
            b = self._o2b[cur_node]
            b.set_styles(self.NODE_TEXT_NORMAL, self.NODE_RECT_NORMAL)

        if node is not None:
            b = self._o2b[node]
            b.set_styles(self.NODE_TEXT_SELECTED, self.NODE_RECT_SELECTED)

        self._node = node

        self.event_generate("<<Node>>")

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
            self.edge = None
            self._co_visualize = None
            self.cancel_task(co)
            self._cnv.delete(ALL)
            self._cnv.update_scroll_region()
            del self._o2iid
            del self._o2b
            del self._iid2o
            del self._dgp
            dismiss(self._on_node_placed)
            dismiss(self._on_edge_placed)
            del self._jobs

        if p is None:
            return

        self._repo = Repo(p)

        self._co_visualize = co = self.co_visualize()
        self.enqueue(co)

    def _co_worker(self):
        jobs = self._jobs
        pop = jobs.popleft
        while jobs:
            yield True
            pop()()

    def co_visualize(self):
        self._o2iid = {}
        self._o2b = {}
        self._iid2o = {}
        self._g = Grid()
        self._jobs = deque()

        self._dgp = dgp = DynamicGraphPlacer2D()

        listen(dgp, "node", self._on_node_placed)
        listen(dgp, "edge", self._on_edge_placed)

        mg = GitMacrograph(self._repo)

        mg.watch_node(self._on_mg_node)
        mg.watch_edge(self._on_mg_edge)

        print("Building GitMacrograph")

        for i in mg.co_build(
            refs_iter_func = REFS_ORDER_RECENT_FIRST,
        ):
            yield i
            while dgp.has_work:
                yield dgp.co_place()
                # do layout updates
                while self._jobs:
                    yield self._co_worker()
            while self._jobs:
                yield self._co_worker()

        # place last added items
        while dgp.has_work:
            yield self._co_worker()
            yield dgp.co_place()

        print("Doing rest jobs...")

        while self._jobs:
            yield self._co_worker()

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
            if split is self._edge:
                # discard selection
                self.edge = None

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
        o2b = self._o2b
        iid2o = self._iid2o

        # logical coordinates
        lxy = dgp.node_coords(n)

        try:
            b = o2b[n]
        except KeyError:
            if lxy is None:
                # removed
                return
            b = TextGridBox(cnv)
            o2b[n] = b
            for iid in b.iter_iids():
                iid2o[iid] = n
        else:
            if lxy is None:
                # removed
                b.delete()
                del o2b[n]
                for iid in b.iter_iids():
                    del iid2o[iid]

                return

        if isinstance(n, GitMgNode):
            b.set_text(n.pretty)
            b.set_styles(
                self.NODE_TEXT_SELECTED if self._node is n
                    else self.NODE_TEXT_NORMAL,
                self.NODE_RECT_SELECTED if self._node is n
                    else self.NODE_RECT_NORMAL
            )
        elif isinstance(n, GitMgEdge):
            l = len(n)
            # assert l  # just print a warning instead
            if not l:
                print("Error: len(GitMgEdge) == 0 should not be placed")
            b.set_text(str(l))
            b.set_styles(
                self.EDGE_TEXT_SELECTED if self._edge is n
                    else self.EDGE_TEXT_NORMAL,
                self.EDGE_RECT_SELECTED if self._edge is n
                    else self.EDGE_RECT_NORMAL
            )
        else:
            raise RuntimeError(type(n))

        b.g = self._g
        b.gcoords = lxy

    def _on_edge_placed(self, *ab):
        o2b = self._o2b

        gcoords = []
        gcoord = gcoords.append

        for lx, ly in self._dgp.iter_edge_coords(*ab):
            gcoord(lx)
            gcoord(ly)

        if gcoords:
            try:
                l = o2b[ab]
            except KeyError:
                l = GridLine(self._cnv, gcoords)
            else:
                l.set_gcoords = gcoords
            l.g = self._g
        else:
            # removed
            l = o2b.pop(ab, None)
            if l is not None:
                l.remove()

    def _on_item_b1(self, e):
        iid2o = self._iid2o
        cnv = self._cnv
        for iid in cnv.find_closest(cnv.canvasx(e.x), cnv.canvasy(e.y)):
            o = iid2o.get(iid)
            if isinstance(o, GitMgEdge):
                self.edge = o
                break
            elif isinstance(o, GitMgNode):
                self.node = o
                break



def gev_col_message(commit):
    "Commit Message"
    return commit.message.splitlines()[0]

gev_col_message.__width__ = 600

def gev_col_author_name(commit):
    "Author"
    return commit.author.name

def gev_col_author_email(commit):
    "Author E-mail"
    return commit.author.email

def gev_col_authored_timestamp(commit):
    "Authored Timestamp"
    return str(commit.authored_datetime)

def gev_col_committer_name(commit):
    "Committer"
    return commit.committer.name

def gev_col_committer_email(commit):
    "Committer E-mail"
    return commit.committer.email

def gev_col_committed_timestamp(commit):
    "Committed Timestamp"
    return str(commit.committed_datetime)


GEV_ALL_COLUMNS = (
    gev_col_message,
    gev_col_author_name,
    gev_col_author_email,
    gev_col_authored_timestamp,
    gev_col_committer_name,
    gev_col_committer_email,
    gev_col_committed_timestamp,
)


class GEVWidget(GUIFrame):
    """ Git Edge View Widget
    """

    def __init__(self, *a, **kw):
        sizegrip = kw.pop("sizegrip", False)
        columns = kw.pop("columns", GEV_ALL_COLUMNS)

        GUIFrame.__init__(self, *a, **kw)

        self._columns = columns
        self._repo_path = None
        self._co_visualize = None

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)

        self._tv = tv = VarTreeview(self,
            columns = tuple(c.__name__ for c in columns),
            selectmode = BROWSE,
        )

        tv.column("#0", minwidth = 10, width = 85, stretch = False)
        tv.heading("#0", text = "ID")

        for col in columns:
            colkw = dict(
                minwidth = getattr(col, "__minwidth__", 10),
                # TODO: more settings?
            )
            if hasattr(col, "__width__"):
                colkw["width"] = col.__width__
            tv.column(col.__name__, **colkw)
            tv.heading(col.__name__, text = col.__doc__)

        tv.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(self, tv, sizegrip = sizegrip)

        self._edge = None
        self._c2iid = c2iid = bidict()
        self._iid2c = c2iid.mirror
        self._commit = None

        tv.bind("<<TreeviewSelect>>", self._on_tv_select, "+")

    def _on_tv_select(self, e):
        tv = self._tv
        iid2c = self._iid2c

        for iid in tv.selection():
            try:
                c = iid2c[iid]
            except KeyError:
                continue

            self.commit = c
            break

    @property
    def commit(self):
        return self._commit

    @commit.setter
    def commit(self, commit):
        if self._commit is commit:
            return
        self._commit = commit

        iid = self._c2iid.get(commit)

        if iid is None:
            self._tv.selection_set()
        else:
            self._tv.selection_set(iid)

        self.event_generate("<<Commit>>")

    @property
    def edge(self):
        return self._edge

    @edge.setter
    def edge(self, edge):
        if self._edge is edge:
            return
        self._edge = edge

        columns = self._columns

        tv = self._tv
        tv.delete(*tv.get_children())

        c2iid = self._c2iid
        c2iid.clear()

        if edge is not None:
            for c in edge:
                commit = c._mg._repo.commit(c.sha)
                c2iid[c] = tv.insert("",
                    index = 0,
                    text = str(c.sha[:8]),
                    values = list(column(commit) for column in columns),
                )

        iid = c2iid.get(self._commit)
        if iid is not None:
            tv.selection_set(iid)


class GEVWindow(VarToplevel):

    def __init__(self, *a, **kw):
        VarToplevel.__init__(self, *a, **kw)

        self.title("Git Edge Viewer")

        self._gevw = gevw = GEVWidget(self,
            sizegrip = True,
        )
        gevw.pack(
            fill = BOTH,
            expand = True,
        )

    @property
    def edge(self):
        return self._gevw.edge

    @edge.setter
    def edge(self, edge):
        self._gevw.edge = edge

    @property
    def commit(self):
        return self._gevw.commit

    @commit.setter
    def commit(self, commit):
        self._gevw.commit = commit


_recursion = object()

class GGVWindow(GUITk):

    def __init__(self, repo):
        GUITk.__init__(self)
        self.title(_("Git Graph Viewer"))

        self._ggvw = ggvw = GGVWidget(self, sizegrip = True)
        ggvw.pack(fill = BOTH, expand = True)

        ggvw.bind("<<Edge>>", self._on_edge, "+")
        ggvw.bind("<<Node>>", self._on_node, "+")

        self._gevw = gevw = GEVWindow(self)
        gevw.bind("<<Commit>>", self._on_commit, "+")

        # print("repo = " + repo)
        ggvw.repo_path = repo

        with MenuBuilder(self) as menubar:
            with menubar(_("Windows")) as windows_menu:
                self._v_gevw = v = BooleanVar(self)
                windows_menu(gevw.title(), variable = v)
                HideShowBinding(gevw, v)

        self._commit = None

    @property
    def commit(self):
        return self._commit

    @commit.setter
    def commit(self, commit):
        if self._commit in (commit, _recursion):
            return
        self._commit = _recursion

        ggvw = self._ggvw
        gevw = self._gevw

        # Note, assigments below may trigger _on_node/_on_commit while
        # this setter is already called by _on_commit/_on_node.
        # It overrides the assignment.
        # `_recursion` check prevents this.

        gevw.commit = commit

        if commit is None:
            ggvw.node = None
        else:
            if commit.is_macronode:
                ggvw.node = commit
            else:
                ggvw.node = None

        self._commit = commit

        self.event_generate("<<Commit>>")

    def _on_edge(self, e):
        edge = e.widget.edge
        self._gevw.edge = [edge._ancestor] + edge + [edge._descendant]
        self._v_gevw.set(True)

    def _on_node(self, e):
        self.commit = self._ggvw.node

    def _on_commit(self, e):
        self.commit = self._gevw.commit


def main():
    ap = ArgumentParser(description = "Git Graph Viewer")
    ap.add_argument("repo")

    args = ap.parse_args()

    root = GGVWindow(**vars(args))
    root.geometry("900x900")
    root.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
