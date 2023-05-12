from argparse import (
    ArgumentParser
)
from six.moves.tkinter import (
    BOTH
)
from git import (
    Repo
)
from common import (
    CommitDesc,
    ee,
    mlget as _
)
from widgets import (
    add_scrollbars_native,
    DnDGroup,
    ANCHOR_MIDDLE,
    CanvasDnD,
    GUIFrame,
    GUITk
)
from collections import (
    defaultdict,
)
from graphviz import (
    Digraph
)


# Set this env. var. to output macrograph to file in Graphviz format.
DOT_FILE_NAME = ee("GIT_GRAPH_DOT_FILE_NAME", None)


def gen_macrograph_gv(macrograph):
    graph = Digraph(
        name = "Git Macrograph",
        graph_attr = dict(
            rankdir = "BT",
        ),
        node_attr = dict(
            shape = "polygon",
            fontname = "Momospace",
        ),
        edge_attr = dict(
            style = "filled"
        ),
    )

    # cache
    node = graph.node
    edge = graph.edge

    sha2node = {}

    for sha in macrograph:
        n = "n%d" % len(sha2node)
        sha2node[sha] = n
        node(n, label = sha)

    # intermediate nodes contain amount of commits between macronodes
    intermediate = 0

    for p, descendants in macrograph.items():
        for d, tracks in descendants.items():
            for t in tracks:
                tlen = len(t)
                if tlen:
                    n = "e%d" % intermediate
                    intermediate += 1
                    node(n, label = str(tlen))
                    edge(sha2node[p], n)
                    edge(n, sha2node[d])
                else:
                    edge(sha2node[p], sha2node[d])

    return graph


def gen_macrograph_gv_source(macrograph):
    return gen_macrograph_gv(macrograph).source


def gen_macrograph_gv_file(macrograph, file_name):
    source = gen_macrograph_gv_source(macrograph)
    with open(file_name, "w") as f:
        f.write(source)


class GGVWidget(GUIFrame):

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

        co = self._co_visualize
        if co is not None:
            # TODO: full cleanup
            self.cancel_task(co)

        self._repo_path = p
        self._repo = Repo(p)

        self._co_visualize = co = self.co_visualize()
        self.enqueue(co)

    def co_visualize(self):
        self._commits = commits = {}

        print("Building Git Graph")
        yield CommitDesc.co_build_git_graph(self._repo, commits)
        print("Done")

        yield True
        print("Searching for macronodes")
        nodes = {}

        for c in commits.values():
            if c.is_merge or c.is_fork or c.is_leaf or c.is_root:
                nodes[c.sha] = c

        print("Done")

        yield True
        print("Building macro graph")
        # Edges between nodes
        macrograph = dict((sha, defaultdict(list)) for sha in nodes)

        m_count = len(macrograph)
        print("Macronodes count : %d" % m_count)

        for i, n in enumerate(nodes.values(), 1):
            yield True
            stack = list(
                (
                    [p],  # track from n
                    p,
                ) for p in n.parents
            )
            while stack:
                t, p = stack.pop()
                if p.sha in nodes:
                    macrograph[p.sha][n.sha].append(t)
                    continue

                pparents = p.parents

                assert len(pparents) == 1, "%s: `.sha` must be in `nodes`" % p

                pp = pparents[0]
                t.append(pp)
                stack.append((t, pp))

            print("%d/%d" % (i, m_count))

        print("Done")

        if DOT_FILE_NAME is not None:
            print("Writing Graphviz file: " + DOT_FILE_NAME)
            gen_macrograph_gv_file(macrograph, DOT_FILE_NAME)
            print("Done")

        return
        # TODO: the code below is not actual

        print("Laying out Graph")

        rest = set(macrograph)

        cnv = self._cnv

        x, y = cnv.winfo_width() / 2, cnv.winfo_height() / 2
        positions = {}
        dnd_groups = {}
        bbox = x, y, x, y

        while True:
            # get any node as starting
            for n_sha in rest:
                break
            else:
                # Nothing left
                break

            n = nodes[n_sha]
            stack = [n]

            x, y = next(iter_sides(bbox, spacing = 50))
            positions[n_sha] = x, y
            n_oval = cnv.create_oval(x, y, x + 10, y + 10,
                tags = "DnD",
                fill = "white"
            )
            dnd_groups[n_sha] = DnDGroup(cnv, n_oval, [])

            bbox = (
                min(x, bbox[0]), min(y, bbox[1]),
                max(x + 10, bbox[2]), max(y + 10, bbox[3]),
            )

            while stack:
                n = stack.pop()
                n_sha = n.sha
                try:
                    rest.remove(n_sha)
                except KeyError:
                    # already visited
                    continue

                cnv.update_scroll_region()
                yield True

                nx, ny = positions[n_sha]
                n_dnd = dnd_groups[n_sha]

                children = macrograph[n_sha]
                for c_sha in children:
                    try:
                        x, y = positions[c_sha]
                    except KeyError:
                        sides = iter(iter_sides(bbox))
                        nearest = x, y = next(sides)
                        nearest_dst = (nx - x) ** 2, (ny - y) ** 2

                        for x, y in sides:
                            cnv_dst = (nx - x) ** 2, (ny - y) ** 2
                            if cnv_dst < nearest_dst:
                                nearest_dst = cnv_dst
                                nearest = x, y

                        positions[c_sha] = nearest

                        x, y = nearest
                        c_oval = cnv.create_oval(
                            x, y, x + 10, y + 10,
                            tags = "DnD",
                            fill = "white"
                        )
                        dnd_groups[c_sha] = c_dnd = DnDGroup(cnv, c_oval, [])

                        bbox = (
                            min(x, bbox[0]), min(y, bbox[1]),
                            max(x + 10, bbox[2]), max(y + 10, bbox[3]),
                        )
                    else:
                        c_dnd = dnd_groups[c_sha]

                    # print(n_sha, "->", c_sha)

                    x1, y1 = nx + 5, ny + 5
                    x2, y2 = x + 5, y + 5
                    line_id = cnv.create_line(x1, y1, x2, y2)
                    cnv.tag_lower(line_id)
                    n_dnd.add_item(line_id, 0, 2)
                    c_dnd.add_item(line_id, 2, 4)

                    tx, ty = (x1 + x2) / 2, (y1 + y2) / 2

                    text_iid = cnv.create_text(tx + 5, ty - 5,
                        text = str(children[c_sha])
                    )

                    DnDGroup(cnv, line_id, [text_iid],
                        anchor_point = ANCHOR_MIDDLE
                    )

                    stack.append(nodes[c_sha])

        print("Done")
        cnv.update_scroll_region()


def iter_sides(bbox, spacing = 20):
    x, y, X, Y = bbox
    x -= spacing
    y -= spacing
    X += spacing
    Y += spacing
    xm = (x + X) / 2
    ym = (y + Y) / 2

    if X - x > Y - y:
        yield xm, y
        yield xm, Y
        yield X, ym
        yield x, ym
    else:
        yield X, ym
        yield x, ym
        yield xm, y
        yield xm, Y


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
