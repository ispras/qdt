"Dynamic graph layout example"

from libe.common.events import (
    listen,
)
from libe.graph.dynamic_placer import (
    DynamicGraphPlacer2D,
)
from widgets.DnDCanvas import (
    bbox2screen,
    CanvasDnD,
)

from six.moves.tkinter import (
    BOTH,
    Tk,
)

STEP_SZ = 30
RECT_SZ = 15
GRAPH_OFFSET = None


def co_main_script(dgp):
    # shortcuts
    e = dgp.add_edge
    n = dgp.add_node
    r = dgp.remove_node

    n("A")
    n("B")
    e("A", "B")

    yield

    n("C")
    n("D")
    e("D", "C")

    yield

    e("A", "C")

    yield

    n(1)
    n(2)
    n(3)
    n(4)
    e(1, 2)
    e(2, 3)
    e(3, 4)
    n(5)
    e(3, 5)

    yield

    e(2, "A")

    yield

    n("!")
    e("B", "!")

    yield

    n("?")
    e(3, "?")

    yield

    e("D", 1)
    yield

    e(2, "!")
    yield

    e(3, "!")
    yield

    e(1, "C")
    yield

    e(1, "!")
    yield

    r("!")
    yield

    e(4, "?")
    yield

    e("?", 4)
    yield

    n("x")
    n("y")
    n("z")
    e("x", "y")
    e("y", "z")
    e("z", "x")
    yield

    r(4)
    yield

    r("x")
    yield

    r("y")
    yield

    r("z")
    yield

    n("x")
    yield

    e(5, "x")
    yield


def co_script(dgp, cnv):
    for __ in co_main_script(dgp):
        dgp.place()
        yield

    while True:
        yield


class TestDynamicGraphPlacer2D(DynamicGraphPlacer2D):
    preferred_direction = (1, 1)


def main():
    dgp = TestDynamicGraphPlacer2D()

    root = Tk()
    cnv = CanvasDnD(root,
        width = 800,
        height = 800,
        background = "white",
    )
    cnv.pack(fill = BOTH, expand = True)

    script_iter = iter(co_script(dgp, cnv))

    root.bind("<Return>", lambda _: next(script_iter))
    root.bind("<KP_Enter>", lambda _: next(script_iter))

    o2iid = {}

    rect_sz_2 = RECT_SZ / 2
    offset = GRAPH_OFFSET

    if offset is None:
        ox = rect_sz_2 + 1
        oy = rect_sz_2 + 1
    else:
        ox, oy = offset

    def _on_node(n):
        try:
            (riid, tiid) = o2iid[n]
        except KeyError:
            riid = cnv.create_rectangle(0, 0, 0, 0, fill = "white")
            tiid = cnv.create_text(0, 0, text = str(n))
            o2iid[n] = (riid, tiid)

        # logical coordinates
        lxy = dgp.node_coords(n)

        if lxy is None:
            # removed
            cnv.delete(riid, tiid)
            del o2iid[n]
            return

        lx, ly = lxy

        # pixel coordinates
        px = ox + STEP_SZ * lx
        py = oy + STEP_SZ * ly

        cnv.coords(riid,
            px - rect_sz_2,
            py - rect_sz_2,
            px + rect_sz_2,
            py + rect_sz_2,
        )
        cnv.coords(tiid, px, py)
        bbox2screen(cnv)

    def _on_edge(*ab):
        try:
            iid = o2iid[ab]
        except KeyError:
            iid = cnv.create_line(0, 0, 0, 0)
            o2iid[ab] = iid
            cnv.lower(iid)

        coords = []
        coord = coords.append

        for lx, ly in dgp.iter_edge_coords(*ab):
            px = ox + STEP_SZ * lx
            py = oy + STEP_SZ * ly
            coord(px)
            coord(py)

        if coords:
            cnv.coords(iid, coords)
        else:
            del o2iid[ab]
            cnv.delete(iid)
        bbox2screen(cnv)

    listen(dgp, "node", _on_node)
    listen(dgp, "edge", _on_edge)

    root.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
