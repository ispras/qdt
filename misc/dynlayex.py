"Dynamic graph layout example"

from libe.graph.dynamic_placer import (
    DynamicGraphPlacer2D,
)

from six.moves.tkinter import (
    BOTH,
    Canvas,
    CENTER,
    Tk,
)

def draw_graph(dgp, cnv, step_sz = 30, rect_sz = 15, offset = None):
    prev = cnv.find_all()

    rect_sz_2 = rect_sz / 2

    if offset is None:
        ox = rect_sz_2 + 1
        oy = rect_sz_2 + 1
    else:
        ox, oy = offset

    rect = cnv.create_rectangle
    text = cnv.create_text
    line = cnv.create_line

    grid = dgp._g
    for ij, cmp in dgp._components.items():
        # cell grid x/y
        cgx, cgy = grid(ij)
        l, t = cmp.aabb[:2]
        cgx -= l
        cgy -= t

        for e in cmp._edges:
            coords = []
            coord = coords.append

            for egx, egy in e:
                # global edge grid x/y
                gegx = egx + cgx
                gegy = egy + cgy

                x = gegx * step_sz + ox
                y = gegy * step_sz + oy

                coord(x)
                coord(y)

            line(*coords)

        for n, (ngx, ngy) in cmp._nodes.items():
            # global node grid x/y
            gngx = ngx + cgx
            gngy = ngy + cgy

            x = gngx * step_sz + ox
            y = gngy * step_sz + oy

            rect(
                x - rect_sz_2,
                y - rect_sz_2,
                x + rect_sz_2,
                y + rect_sz_2,
                fill = "white",
            )
            text(x, y,
                text = n,
                anchor = CENTER,
            )

    if prev:
        cnv.delete(*prev)


def co_main_script(dgp):
    # shortcuts
    e = dgp.add_edge
    n = dgp.add_node

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


def co_script(dgp, cnv):
    for __ in co_main_script(dgp):
        dgp.place()
        draw_graph(dgp, cnv)
        yield

    while True:
        yield


class TestDynamicGraphPlacer2D(DynamicGraphPlacer2D):
    preferred_direction = (1, 1)


def main():
    dgp = TestDynamicGraphPlacer2D()

    root = Tk()
    cnv = Canvas(root, background = "white")
    cnv.pack(fill = BOTH, expand = True)

    script_iter = iter(co_script(dgp, cnv))

    root.bind("<Return>", lambda _: next(script_iter))
    root.bind("<KP_Enter>", lambda _: next(script_iter))

    root.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
