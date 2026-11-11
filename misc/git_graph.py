from common import (
    bidict,
    dismiss,
    DynamicGraphPlacer2D,
    ee,
    E_GIT_FOUND,
    E_GIT_DISCARD_FOUND,
    file_name_safe,
    FormatVar,
    git_feature_commit_hexsha,
    GitSearchRequest,
    GitSearchRuntime,
    Grid,
    GridRect,
    listen,
    makedirs,
    mlget as _,
    MurMur,
    pypath,
    ready,
    RectSpring,
    REFS_ORDER_RECENT_FIRST,
)
from widgets import (
    add_scrollbars_native,
    asksaveas,
    askyesno,
    CanvasDnD,
    CanvasTextMeasurer,
    ColorGenerator,
    CommitInfoToplevel,
    EntryDialog,
    GUIFrame,
    GUITk,
    GUIToplevel,
    HideShowBinding,
    LEFT_BOTTOM,
    LineSelectDialog,
    MenuBuilder,
    PatchEditorFrame,
    POLY_BASES,
    QDTUserSettings,
    Spot,
    tk_delayed,
    TkPopupHelper,
    VarMenu,
    VarTreeview,
)
from common.git.macrograph import (
    GitMacrograph,
    GitMgEdge,
    GitMgNode,
)

from argparse import (
    ArgumentParser,
)
from collections import (
    defaultdict,
    namedtuple,
)
from git import (
    Repo,
)
from os.path import (
    abspath,
    dirname,
    isdir,
    join,
)
from six.moves.tkinter import (
    ALL,
    BOTH,
    BooleanVar,
    BROWSE,
    StringVar,
)
with pypath("..unidiff"):
    from unidiff import (
        PatchSet,
    )


SpotConfig = namedtuple("SpotConfig", "base fill")


class GitHighlighter(GitSearchRequest):

    def __init__(self, features, criteria, spotcfg):
        super(GitHighlighter, self).__init__(features, criteria)
        self.spotcfg = spotcfg


class SpotGenerator:

    def __init__(self, rng):
        self.rng = rng
        self.cg = ColorGenerator(rng)
        self.skipped = set()

    def __iter__(self):
        return self

    def skip(self, cfg):
        self.skipped.add(cfg)

    def __next__(self):
        rng = self.rng
        cg = self.cg
        skipped = self.skipped
        while True:
            base = POLY_BASES[next(rng) % len(POLY_BASES)]
            ret = SpotConfig(base, "#%02X%02X%02X" % next(cg),)
            if ret not in skipped:
                break
        skipped.add(ret)
        return ret


# Set this env. var. to output macrograph to file in Graphviz format.
DOT_FILE_NAME = ee("GIT_GRAPH_DOT_FILE_NAME", "None")
SPOT_SIZE = ee("GIT_GRAPH_SPOT_SIZE", "10")


class GitGraphSettings(QDTUserSettings):
    _suffix = join("GitGraph", "settings.py")

    def __init__(self):
        super(GitGraphSettings, self).__init__(
            glob = globals(),
            version = 0.1,
            projects = [],
        )


class GitGraphProject:

    def __init__(self,
        repo_path = None,
        name = "",
        highlighters = [],
        spot_gen = None,
        **kw
    ):
        super(GitGraphProject, self).__init__(**kw)
        self.repo_path = repo_path
        self.name = name
        self.highlighters = list(highlighters)
        if spot_gen is None:
            spot_gen = SpotGenerator(MurMur())
        self.spot_gen = spot_gen

    def gen_highlighter(self, features, criteria):
        hl = GitHighlighter(features, criteria, next(self.spot_gen))
        self.highlighters.append(hl)
        return hl


class TextGridBox(GridRect):

    _spot_step = (int(SPOT_SIZE * 1.2) << 1) + 1

    def __kwinit__(self, canvas, iid2b):
        super(TextGridBox, self).__kwinit__((0, 0))
        self._c = canvas
        self._iid2b = iid2b
        self._spots = []
        # First time create items as soon as all ready.
        self.delayed_valid = True

    @ready
    def iids(self, ready):
        iid2b = self._iid2b
        canvas = self._c
        icfg = canvas.itemconfig

        if not ready:
            # Note, thi's GGVWidget specific.
            canvas.master.sig_item_invalid(self)

            # Do not re-create items each time.
            del self.delayed_valid

            self._prev_iids = riid, tiid = self._iids
            # Highlight obsolete configuration items with grey color.
            # So, the canvas does not look empty most of time.
            icfg(riid, outline = "grey")
            icfg(tiid, fill = "grey")
            return

        x, y = self._coords

        cw, ch = self._cell_size

        x += cw // 2
        y += ch // 2

        w, h = self._size
        w_2 = (w - 6) // 2
        h_2 = (h - 6) // 2

        coords = (
            x - w_2,
            y - h_2,
            x + w_2,
            y + h_2
        )

        try:
            riid, tiid = ret = self._prev_iids
        except AttributeError:
            riid = canvas.create_rectangle(
                *coords,
                **self._rect_style
            )
            iid2b[riid] = self

            tiid = canvas.create_text(x, y,
                text = self._text,
                **self._text_style
            )
            iid2b[tiid] = self
            ret = (riid, tiid)
        else:
            icfg(riid, **self._rect_style)
            icfg(tiid, text = self._text, **self._text_style)
            icoords = canvas.coords
            icoords(riid, *coords)
            icoords(tiid, x, y)

        spots = self._spots
        if spots:
            cgen = RectSpring(self._spot_step, x - w // 2, y - h // 2, w, h)
            for spot in spots:
                spot.offset = next(cgen)

        return ret

    coords = iids.bit()
    cell_size = iids.bit()
    size = iids.bit()
    rect_style = iids.bit()
    text_style = iids.bit()
    text = iids.bit()
    delayed_valid = iids.bit()

    def set_text(self, text):
        self.text = text
        w, h = self._c.master.get_text_size(text)
        self.size = (w + 12, h + 12)

    def set_styles(self, text_style, rect_style):
        self.text_style = text_style
        self.rect_style = rect_style

    def update_canvas_coords(self):
        self.delayed_valid = True
        if self._g is not None:
            return
        try:
            iids = self._prev_iids
        except AttributeError:
            return
        del self._prev_iids
        iid2b = self._iid2b
        canvas = self._c
        canvas.delete(*iids)
        for iid in iids:
            del iid2b[iid]
        for spot in self._spots:
            try:
                del spot.offset
            except AttributeError:
                continue


class _GridLinePoint(GridRect):

    def __init__(self, line, size = 10, **kw):
        self._l = line
        super(_GridLinePoint, self).__init__((size, size), **kw)

    @ready
    def master_line_updater(self, ready):
        # Note, thi's GGVWidget specific.
        l = self._l
        l.valid_points += 1 if ready else -1

    coords = master_line_updater.bit()
    cell_size = master_line_updater.bit()


class GridLine(object):

    LINE_NORMAL = dict(
        smooth = True,
        dash = (5, 5),
        fill = "black",
    )

    LINE_HIGHLIGHTED = dict(LINE_NORMAL)
    LINE_HIGHLIGHTED.update(
        dash = "",
    )

    def __init__(self, canvas):
        self._c = canvas
        self.valid_points = 0
        self.line_style = self.LINE_NORMAL
        self.delayed_valid = True

    def update_canvas_coords(self):
        self.delayed_valid = True

    @ready
    def iid(self, ready):
        canvas = self._c
        icfg = canvas.itemconfig
        if not ready:
            # Note, thi's GGVWidget specific.
            canvas.master.sig_item_invalid(self)
            del self.delayed_valid
            self._prev_iid = iid = self._iid
            # Highlight obsolete configuration lines with grey color.
            # So, the canvas does not look empty most of time.
            icfg(iid, fill = "grey")
            return

        all_coords = []
        for p in self._points:
            cw, ch = p._cell_size
            x, y = p.coords
            x += cw / 2
            y += ch / 2
            all_coords.extend((x, y))

        try:
            iid = self._prev_iid
        except AttributeError:
            iid = canvas.create_line(
                *all_coords,
                **self._line_style
            )
            canvas.lower(iid)
        else:
            canvas.coords(iid, *all_coords)
            icfg(iid, **self._line_style)
        return iid

    all_points_valid = iid.bit()
    line_style = iid.bit()
    delayed_valid = iid.bit()

    @ready
    def validity_updater(self, ready):
        if ready:
            if self._valid_points == len(self._points):
                self.all_points_valid = True
                return True
        else:
            if self._validity_updater:
                del self.all_points_valid

    _points = validity_updater.bit()
    valid_points = validity_updater.bit()

    @property
    def highlighted(self):
        return self._highlighted

    _highlighted = False

    @highlighted.setter
    def highlighted(self, highlighted):
        highlighted = bool(highlighted)
        if self._highlighted is highlighted:
            return
        self._highlighted = highlighted
        self.line_style \
            = self.LINE_HIGHLIGHTED if highlighted else self.LINE_NORMAL

    @property
    def highlights(self):
        """ Use bits as different highlight requests.
Do not set `highlighted` directly if `highlights` are used.
        """
        return self._highlights

    _highlights = 0

    @highlights.setter
    def highlights(self, highlights):
        if self._highlights == highlights:
            return
        self._highlights = highlights
        self.highlighted = highlights

    @ready
    def points(self, ready):
        if ready:
            g = self._g
            points = []
            point = points.append
            gciter = iter(self._gcoords)
            for i in gciter:
                j = next(gciter)
                p = _GridLinePoint(self, gcoords = (i, j))
                p.g = g
                point(p)
            return points
        else:
            try:
                iid = self._prev_iid
            except AttributeError:
                pass
            else:
                del self._prev_iid
                self._c.delete(iid)
            for p in self._points:
                p.g = None

    gcoords = points.bit()
    g = points.bit()


class GGVWidget(GUIFrame, CanvasTextMeasurer):
    """Git Graph View Widget
    """

    _spot_align = staticmethod(LEFT_BOTTOM)
    _spot_outline = "black"

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

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)
        self._cnv = cnv = CanvasDnD(self)
        cnv.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(self, cnv, sizegrip = sizegrip)

        cnv.bind("<<DnDMoved>>", self._on_dnd_moved, "+")
        self.bind_to_items("<Button-1>", self._on_item_b1, "+")

        self._edge = None
        self._node = None

        self._oid2spots = defaultdict(list)
        self._s2oid = {}

        # master must be GUITk or have SignalDispatcherTask.
        self.sig_item_invalid = self.master.signal_dispatcher.new_signal(
            self._on_item_invalid,
        )

    def add_spot(self, o, spotcfg):
        oid = id(o)
        oid2b = self._oid2b
        s = Spot(
            align = self._spot_align,
            outline = self._spot_outline,
            scale = SPOT_SIZE,
            **spotcfg._asdict()
        )
        # do not create it on the canvas immediately
        del s.offset
        self._oid2spots[oid].append(s)
        b = oid2b.get(oid, None)
        if b is not None:
            s.canvas = self._cnv
            b._spots.append(s)
            b._invalidate()
        self._s2oid[s] = oid
        return s

    def remove_spot(self, s):
        oid = self._s2oid.pop(s)
        self._oid2spots[oid].remove(s)
        b = self._oid2b.get(oid, None)
        if b is not None:
            del s.canvas
            b._spots.remove(s)
            b._invalidate()

    @tk_delayed
    def _update_canvas_scroll_region(self):
        self._cnv.extend_scroll_region()

    def _on_dnd_moved(self, __):
        self._update_canvas_scroll_region = -100

    def _on_item_invalid(self, item):
        item.update_canvas_coords()
        self._update_canvas_scroll_region = -100

    def bind_to_items(self, *a):
        cnv = self._cnv
        cnv.tag_bind("e", *a)
        cnv.tag_bind("n", *a)

    @property
    def edge(self):
        return self._edge

    @edge.setter
    def edge(self, edge):
        cur_edge = self._edge
        if edge is cur_edge:
            return

        oid2b = self._oid2b

        # `edge` is a `GitMgEdge`, it corresponds to a box (node) on canvas.
        # I.e. it is not a line (edge) on canvas identified by two `id`s.

        if cur_edge is not None:
            b = oid2b[id(cur_edge)]
            b.set_styles(self.EDGE_TEXT_NORMAL, self.EDGE_RECT_NORMAL)
            for lid in self._iter_edge_line_ids(cur_edge):
                try:
                    l = oid2b[lid]
                except KeyError:
                    continue
                l.highlights &= ~1

        if edge is not None:
            b = oid2b[id(edge)]
            b.set_styles(self.EDGE_TEXT_SELECTED, self.EDGE_RECT_SELECTED)
            for lid in self._iter_edge_line_ids(edge):
                try:
                    l = oid2b[lid]
                except KeyError:
                    continue
                l.highlights |= 1

        self._edge = edge

        self.event_generate("<<Edge>>")

    def _iter_edge_line_ids(self, e):
        eid = id(e)
        yield (id(e._descendant), eid)
        yield (eid, id(e._ancestor))

    @property
    def node(self):
        return self._node

    @node.setter
    def node(self, node):
        cur_node = self._node
        if node is cur_node:
            return

        oid2b = self._oid2b

        if cur_node is not None:
            b = self._oid2b[id(cur_node)]
            b.set_styles(self.NODE_TEXT_NORMAL, self.NODE_RECT_NORMAL)
            for lid in self._iter_node_line_ids(cur_node):
                try:
                    l = oid2b[lid]
                except KeyError:
                    continue
                l.highlights &= ~2

        if node is not None:
            b = self._oid2b[id(node)]
            b.set_styles(self.NODE_TEXT_SELECTED, self.NODE_RECT_SELECTED)
            for lid in self._iter_node_line_ids(node):
                try:
                    l = oid2b[lid]
                except KeyError:
                    continue
                l.highlights |= 2

        self._node = node

        self.event_generate("<<Node>>")

    def _iter_node_line_ids(self, n):
        nid = id(n)
        for p in n.parents:
            if p.is_macronode:
                yield (nid, id(p))
            else:
                yield (nid, id(p._edge))
        for c in n.children:
            if c.is_macronode:
                yield (id(c), nid)
            else:
                yield (id(c._edge), nid)

    _dgp = None
    def reset(self):
        self.edge = None

        dgp = self._dgp
        if dgp is not None:
            dgp.stop_bg()
            dismiss(self._on_node_placed)
            dismiss(self._on_edge_placed)

        self._cnv.delete(ALL)
        self._cnv.update_scroll_region()

        self._g = Grid()
        self._oid2b = {}
        self._b2o = {}
        self._iid2b = {}
        self._dgp = dgp = DynamicGraphPlacer2D()
        listen(dgp, "node", self._on_node_placed)
        listen(dgp, "edge", self._on_edge_placed)
        self.enqueue(dgp.co_place_bg())

    def account_mg_node(self, mn):
        self._dgp.add_node(mn)

    def account_mg_edge(self, e, split):
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
        b2o = self._b2o
        oid2b = self._oid2b
        iid2b = self._iid2b
        getspots = self._oid2spots.get

        # logical coordinates
        lxy = dgp.node_coords(n)

        nid = id(n)

        try:
            b = oid2b[nid]
        except KeyError:
            if lxy is None:
                # removed
                return
            b = TextGridBox(cnv, iid2b)
            spots = getspots(nid)
            if spots:
                for s in spots:
                    s.canvas = cnv
                b._spots.extend(spots)
            oid2b[nid] = b
            b2o[b] = n
            b.g = self._g
        else:
            if lxy is None:
                # removed
                b.g = None
                del oid2b[nid]
                del b2o[b]
                for s in b._spots:
                    del s.canvas
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

        b.gcoords = lxy

    def _on_edge_placed(self, *ab):
        oid2b = self._oid2b
        eids = tuple(map(id, ab))

        gcoords = []
        gcoord = gcoords.append

        for lx, ly in self._dgp.iter_edge_coords(*ab):
            gcoord(lx)
            gcoord(ly)

        if gcoords:
            try:
                l = oid2b[eids]
            except KeyError:
                l = GridLine(self._cnv)
                oid2b[eids] = l
                l.g = self._g
            l.gcoords = gcoords
        else:
            # removed
            l = oid2b.pop(eids, None)
            if l is not None:
                l.g = None

    def _on_item_b1(self, e):
        for o in self.iter_items_at(e.x, e.y):
            if isinstance(o, GitMgEdge):
                self.edge = o
                break
            elif isinstance(o, GitMgNode):
                self.node = o
                break

    def iter_items_at(self, x, y):
        cnv = self._cnv
        x = cnv.canvasx(x)
        y = cnv.canvasy(y)
        checked = set()
        check = checked.add
        get_box = self._iid2b.get
        get_obj = self._b2o.get
        for iid in cnv.find_overlapping(x, y, x + 1, y + 1):
            b = get_box(iid)
            if b is None:
                continue
            o = get_obj(b)
            # Because of co_signal delayed update, the box to object mapping
            # can already be removed while a grey box is still visible on
            # the canvas.
            # In that case, `o is None`.
            # Look for `_prev_ids`.
            if o in checked:
                continue
            check(o)
            if isinstance(o, (GitMgEdge, GitMgNode)):
                yield o


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
    gev_col_authored_timestamp,
    gev_col_author_email,
    gev_col_committer_name,
    gev_col_committer_email,
    gev_col_committed_timestamp,
)


class GEVWidget(GUIFrame):
    """ Git Edge View Widget
    """

    def __init__(self, *a, **kw):
        sizegrip = kw.pop("sizegrip", False)
        columns = kw.pop("columns", GEV_ALL_COLUMNS[:3])

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


class GEVWindow(GUIToplevel):

    def __init__(self, *a, **kw):
        topmost = kw.pop("topmost", True)

        GUIToplevel.__init__(self, *a, **kw)

        self.title(_("Git Edge Viewer"))

        self._gevw = gevw = GEVWidget(self,
            sizegrip = True,
        )
        gevw.pack(
            fill = BOTH,
            expand = True,
        )

        if topmost is not None:
            self.topmost = topmost

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



class ExCommitInfoToplevel(
    CommitInfoToplevel,
    TkPopupHelper,
):

    def __init__(self, *a, **kw):
        sizegrip = kw.pop("sizegrip", True)
        # will create its own sizegrip
        kw["sizegrip"] = False
        CommitInfoToplevel.__init__(self, *a, **kw)

        # re-pack, don't expand
        self._cif.pack(fill = BOTH, expand = False)

        self._pef = pef = PatchEditorFrame(self,
            sizegrip = sizegrip,
        )
        pef.pack(fill = BOTH, expand = True)

        pef.bind("<<Button-3-File>>", self._on_b3_file, "+")

        self._file_popup = menu = VarMenu(self, tearoff = False)
        menu.add("command",
            label = _("Diff Tool"),
            command = self._on_file_difftool
        )

        with MenuBuilder(self) as menu:
            with menu(_("Patch")) as patch_menu:
                patch_menu(_("Save"), command = self._on_patch_save)

        self._difftool_processes = []

    _base_commit = CommitInfoToplevel.commit

    def _on_patch_save(self):
        data = self._get_pretty_patch_data()
        if not data:
            return

        commit = self.commit

        for l in data.splitlines():
            if l.startswith(b"Subject:"):
                base_name = l[8:].strip().decode("utf-8", "surrogateescape")
                base_name = file_name_safe(base_name, forbidden = " ")
                break
        else:
            base_name = commit.hexsha + ".patch"

        proj = self.master._proj

        save_patch_dir = getattr(proj, "save_patch_dir", None)
        if save_patch_dir is None or not isdir(save_patch_dir):
            save_patch_dir = commit.repo.working_tree_dir
        initial_file = join(save_patch_dir, base_name + ".patch")

        prev_topmost = self.topmost
        if prev_topmost:
            self.topmost = False

        try:
            file_path = asksaveas(self,
                [(_("Git patch"), ".patch")],
                title = _("Save patch to file"),
                initial_file = initial_file,
            )
        finally:
            if prev_topmost:
                self.topmost = True

        if not file_path:
            return
        save_patch_dir = dirname(file_path)
        proj.save_patch_dir = save_patch_dir
        makedirs(save_patch_dir, exist_ok = True)
        with open(file_path, "wb") as f:
            f.write(data)

    def _get_pretty_patch_data(self):
        commit = self.commit
        if commit is None:
            return
        data = commit.repo.git.diff_tree(commit,
            stdout_as_string = False,
            pretty = "email",
            color = False,
            patch = True,
            textconv = True,
            find_copies = True,
            commit_id = False,
            unified = 3,
            root = True,
        )
        return data

    def _on_b3_file(self, __):
        self.show_popup(
            self.winfo_pointerx(),
            self.winfo_pointery(),
            self._file_popup,
            tag = self._pef.current_file
        )

    def _on_file_difftool(self):
        self.notify_popup_command()
        pef = self._pef
        file = pef.patch_set[pef.current_file]
        if file.is_binary_file:
            return
        commit = self._base_commit
        if file.is_removed_file:
            f_path = file.source_file
        else:
            f_path = file.target_file
        try:
            parent = commit.parents[0]
        except IndexError:
            # https://stackoverflow.com/a/40884093
            # empty tree
            parent = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        # Cut "a/" ot "b/" prefix off.
        f_path = f_path[2:]
        p = commit.repo.git.difftool(
            parent,
            commit,
            "--",
            f_path,
            # don't wait for termination
            as_process = True,
        )
        # Else, it is immediately interrupted.
        self._difftool_processes.append(p)

    @property
    def commit(self):
        return self._base_commit

    @commit.setter
    def commit(self, commit):
        if commit is self._base_commit:
            return
        self._base_commit = commit
        patch_data = commit.repo.git.diff_tree(commit,
            color = False,
            # pass same options to diff-tree as gitk
            r = True,
            p = True,
            textconv = True,
            submodule = True,
            C = True,
            cc = True,
            commit_id = False,
            unified = 3,
            root = True,
        )
        patch_set = PatchSet.from_string(patch_data)
        pef = self._pef
        pef.patch_set = patch_set
        if patch_set:
            pef.select_file(0)


_recursion = object()

class GGVWindow(GUITk, TkPopupHelper):

    def __init__(self, settings, repo):
        GUITk.__init__(self)

        self._settings = settings

        self._v_name = v_name = StringVar(self)
        self._v_repo_path = v_repo_path = StringVar(self)
        v_title = FormatVar(value = "%s: %s - %s") % (
            v_name,
            v_repo_path,
            _("Git Graph Viewer")
        )
        self.title(v_title)

        self._ggvw = ggvw = GGVWidget(self, sizegrip = True)
        ggvw.pack(fill = BOTH, expand = True)

        ggvw.bind("<<Edge>>", self._on_edge, "+")
        ggvw.bind("<<Node>>", self._on_node, "+")
        ggvw.bind_to_items("<ButtonRelease-3>", self._on_ggvw_item_b3, "+")

        self._gevw = gevw = GEVWindow(self)
        gevw.bind("<<Commit>>", self._on_commit, "+")

        self._cit = cit = ExCommitInfoToplevel(self,
            topmost = True,
        )

        with MenuBuilder(self) as menubar:
            with menubar(_("Project")) as project_menu:
                project_menu(_("Rename"),
                    command = self._on_project_rename,
                )

                project_menu()

                project_menu(_("New"),
                    command = self._on_project_new,
                )
                project_menu(_("Select"),
                    command = self._on_project_select,
                )
                project_menu(_("Delete"),
                    command = self._on_project_delete,
                )

            with menubar(_("Windows")) as windows_menu:
                self._v_gevw = v = BooleanVar(self)
                windows_menu(gevw.title(), variable = v)
                HideShowBinding(gevw, v)

                self._v_cit = v = BooleanVar(self)
                windows_menu(cit.title(), variable = v)
                HideShowBinding(cit, v)

        with MenuBuilder(self, assign = False, tearoff = False) as menu:
            self._popup_ggvw_node = menu.menu
            menu(_("Highlight"),
                command = self._on_popup_ggvw_node_highlight,
            )

        self._commit = None

        self._cosr = cosr = GitSearchRuntime(self)
        listen(cosr, E_GIT_FOUND, self._on_git_found)
        listen(cosr, E_GIT_DISCARD_FOUND, self._on_git_discard_found)

        self._hexsha2mn = {}
        self._res2spot = {}

        self._provide_project(repo)

    def _on_popup_ggvw_node_highlight(self):
        n = self.current_popup_tag
        self.add_highlighter(git_feature_commit_hexsha,
            hexsha = n.sha,
        )
        self.notify_popup_command()

    def _on_ggvw_item_b3(self, e):
        for o in self._ggvw.iter_items_at(e.x, e.y):
            if isinstance(o, GitMgNode):
                break
        else:
            return
        self.show_popup(e.x_root, e.y_root, self._popup_ggvw_node, o)

    def add_highlighter(self, *features, **criteria):
        hl = self._proj.gen_highlighter(features, criteria)
        self._cosr.account_request(hl)

    __proj = None
    @property
    def _proj(self):
        return self.__proj

    @_proj.setter
    def _proj(self, _proj):
        if self.__proj is _proj:
            return
        cosr = self._cosr
        self.__proj = _proj
        self.commit = None
        self._v_name.set(_proj.name or _("nameless").get())
        repo_path = _proj.repo_path
        v_repo_path = self._v_repo_path
        if v_repo_path.get() != repo_path:
            cosr.cleanup()
            v_repo_path.set(repo_path)
            co = self.__co_build_mg
            if co is not None:
                self.cancel_task(co)
            self._ggvw.reset()
            self._repo = Repo(repo_path)
            self.__co_build_mg = co = self._co_build_mg()
            self.enqueue(co)
        else:
            cosr.remove_all_requests()
        # print("repo = " + repo_path)
        cosr.account_requests(*_proj.highlighters)

    def _on_project_rename(self):
        new_name = EntryDialog(
            title = _("Enter project name"),
            value = self.__proj.name,
        ).wait()
        self.__proj.name = new_name
        self._v_name.set(new_name or _("nameless").get())

    def _on_project_new(self):
        proj = GitGraphProject(
            repo_path = self.__proj.repo_path,
        )
        self._settings.projects.append(proj)
        self._proj = proj

    def _on_project_select(self):
        cur_proj = self.__proj
        line2proj = {}
        for proj in self._settings.projects:
            if proj is cur_proj:
                continue
            l =  proj.repo_path + " : " + (proj.name or _("nameless").get())
            while l in line2proj:
                # User is self responsible for it...
                l += " "
            line2proj[l] = proj
        if not line2proj:
            return
        selected_line = LineSelectDialog(
            title = _("Select another project"),
            lines = sorted(line2proj),
            getline = True,
        ).wait()
        self._proj = line2proj.get(selected_line, cur_proj)

    def _on_project_delete(self):
        cur_proj = self.__proj
        if not askyesno(self,
            _("Delete current project?"),
            _("Name: %s\nRepo: %s") % (
                cur_proj.name or _("nameless"), cur_proj.repo_path
            ),
        ):
            return
        cur_repo_path = cur_proj.repo_path
        self._settings.projects.remove(cur_proj)
        self._provide_project(cur_repo_path)

    def _provide_project(self, repo_path):
        settings = self._settings

        repo = abspath(repo_path)
        for proj in settings.projects:
            if proj.repo_path == repo:
                break
        else:
            proj = GitGraphProject(
                repo_path = repo,
            )
            settings.projects.append(proj)

        self._proj = proj

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
        self._cit.commit = commit.commit

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
        self._v_cit.set(True)

    def _on_git_found(self, result):
        hexsha = result.commit.hexsha
        mn = self._hexsha2mn[hexsha]
        if False:
            print("highlight", hexsha, type(mn).__name__, id(mn))
        self._res2spot[result] = self._ggvw.add_spot(mn, result.req.spotcfg)

    def _on_git_discard_found(self, result):
        if False:
            hexsha = result.commit.hexsha
            mn = self._hexsha2mn[hexsha]
            print("highligh cancel", hexsha, mn.__type__.__name__, id(mn))
        s = self._res2spot.pop(result)
        self._ggvw.remove_spot(s)

    def _on_mg_node(self, mg, mn):
        self._ggvw.account_mg_node(mn)
        commit = mn.commit
        self._hexsha2mn[commit.hexsha] = mn
        self._cosr.account_commits(commit)

    def _on_mg_edge(self, mg, e, split):
        self._ggvw.account_mg_edge(e, split)
        commits = tuple(mn.commit for mn in e)
        h2mn = self._hexsha2mn
        cosr = self._cosr
        account_commits = cosr.account_commits
        get_ress = cosr.get_commit_results
        if split is None:
            account_commits(*commits)
            for c in commits:
                h2mn[c.hexsha] = e
        else:
            add_spot = self._ggvw.add_spot
            remove_spot = self._ggvw.remove_spot
            res2spot = self._res2spot
            for c in commits:
                hexsha = c.hexsha
                prev_e = h2mn[hexsha]
                assert prev_e is split
                h2mn[hexsha] = e
                ress = get_ress(c)
                if not ress:
                    continue
                if False:
                    print("move highlight", hexsha,
                        type(prev_e).__name__, id(prev_e),
                        "to",
                        type(e).__name__, id(e)
                    )
                for res in ress:
                    remove_spot(res2spot.pop(res))
                    res2spot[res] = add_spot(e, res.req.spotcfg)

    __co_build_mg = None
    def _co_build_mg(self):
        mg = GitMacrograph(self._repo)

        mg.watch_node(self._on_mg_node)
        mg.watch_edge(self._on_mg_edge)

        print("Building GitMacrograph")

        yield mg.co_build(
            refs_iter_func = REFS_ORDER_RECENT_FIRST,
        )

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


def main():
    ap = ArgumentParser(description = "Git Graph Viewer")
    ap.add_argument("repo")

    args = ap.parse_args()

    with GitGraphSettings() as settings:
        print("settings: " + settings.file_name)
        root = GGVWindow(
            settings,
            **vars(args)
        )
        root.geometry("900x900")
        root.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
