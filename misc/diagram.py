from six.moves.tkinter import (
    Tk,
    ALL,
    Text,
    END,
    BOTH
)
from widgets import (
    CanvasDnD,
    CanvasFrame,
    add_scrollbars_native
)
from bisect import (
    insort
)


def owerlaps(bbox1, bbox2):
    if bbox1[2] < bbox2[0]:
        return False
    if bbox2[2] < bbox1[0]:
        return False
    if bbox1[3] < bbox2[1]:
        return False
    if bbox2[3] < bbox1[1]:
        return False
    return True


NODE_SPACING = 5
TAG_OBSTACLE = "o"

# When a window is added to Canvas, Tkinter requires some time to size it.
SIZING_DELAY = 50


class Diagram(CanvasDnD):

    def __init__(self, *a, **kw):
        CanvasDnD.__init__(self, *a, **kw)

        self._nodes2add = []
        self._nodes2place = []

    def add_node(self, x, y, text = ""):
        self._nodes2add.append((x, y, text))
        if not hasattr(self, "_add_node_after_id"):
            self._add_node_after_id = self.after(SIZING_DELAY,
                self._add_node_after
            )

    def _add_node_after(self):
        if len(self._nodes2add) > 1:
            self._add_node_after_id = self.after(SIZING_DELAY,
                self._add_node_after
            )
        else:
            del self._add_node_after_id

        x, y, text = self._nodes2add.pop(0)
        fr = CanvasFrame(self, x, y)
        t = Text(fr, width = 10, height = 3)
        t.pack(fill = BOTH, expand = True)
        t.insert(END, text)

        self.place_node(fr)

    def place_node(self, node):
        self._nodes2place.append(node)
        if not hasattr(self, "_place_node_after_id"):
            self._place_node_after_id = self.after(SIZING_DELAY,
                self._place_node_after
            )

    def _place_node_after(self):
        if len(self._nodes2place) > 1:
            self._place_node_after_id = self.after(SIZING_DELAY,
                self._place_node_after
            )
        else:
            del self._place_node_after_id
            self.after(SIZING_DELAY, self._update_scroll_after)

        node = self._nodes2place.pop(0)

        # During placement a node should not be an obstacle for itself new
        # position candidate.
        if TAG_OBSTACLE in self.gettags(node.id):
            self.dtag(node.id, TAG_OBSTACLE)

        # Account current position and size during placement.
        px, py = self.coords(node.id)
        x, y = self.get_place(
            w = node.winfo_width(),
            h = node.winfo_height(),
            px = px, py = py
        )
        # Note that, a new node should be treated as an obstacle only
        # after it's placement.
        self.addtag_withtag(TAG_OBSTACLE, node.id)
        self.coords(node.id, x, y)

    def _update_scroll_after(self):
        self.config(scrollregion = self.bbox(ALL))

    def get_place(self, w = 100, h = 100, px = 0, py = 0):
        obstacles = []
        # sort obstacle by distance from preferred location
        for iid in self.find_withtag(TAG_OBSTACLE):
            l, t, r, b = bbox = self.bbox(iid)
            dx = ((r + l) >> 1) - px
            dy = ((b + t) >> 1) - py
            insort(obstacles, (dx * dx + dy * dy, iid, bbox))

        def iter_places():
            # first return preferred place
            yield px, py
            # iterate places around obstacles in clockwise order
            for _, _, bbox in obstacles:
                yield bbox[0], bbox[1] - h - NODE_SPACING
                yield bbox[2] + NODE_SPACING, bbox[1] - h - NODE_SPACING
                yield bbox[2] + NODE_SPACING, bbox[1]
                yield bbox[2] + NODE_SPACING, bbox[3] + NODE_SPACING
                yield bbox[0], bbox[3] + NODE_SPACING
                yield bbox[0] - w - NODE_SPACING, bbox[3] + NODE_SPACING
                yield bbox[0] - w - NODE_SPACING, bbox[1]
                yield bbox[0] - w - NODE_SPACING, bbox[1] - h - NODE_SPACING

        # find a place without overlapping with obstacles
        for x, y in iter_places():
            bbox0 = x, y, (x + w), (y + h)
            for _, _, bbox in obstacles:
                if owerlaps(bbox, bbox0):
                    break # bad position
            else:
                break # non-overlapping position

        return x, y


def main():
    tk = Tk()

    tk.geometry("800x800")

    tk.columnconfigure(0, weight = 1)
    tk.columnconfigure(1, weight = 0)
    tk.rowconfigure(0, weight = 1)
    tk.rowconfigure(1, weight = 1)

    diag = Diagram(tk)
    diag.grid(row = 0, column = 0, sticky = "NESW")

    add_scrollbars_native(tk, diag, sizegrip = True)

    for i in range(10):
        diag.add_node(0, 0, str(i))

    tk.mainloop()


if __name__ == "__main__":
    main()
