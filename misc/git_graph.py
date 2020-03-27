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
        macrograph = dict((sha, {}) for sha in nodes)

        m_count = len(macrograph)
        print("Macronodes count : %d" % m_count)

        for n in nodes.values():
            yield True
            # first digit in the tuple is used to count commits between nodes
            stack = list((0, p) for p in n.parents)
            while stack:
                l, p = stack.pop()
                if p.sha in nodes:
                    macrograph[p.sha][n.sha] = l
                    break
                l += 1
                stack.extend((l, pp) for pp in p.parents)

        print("Done")

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
