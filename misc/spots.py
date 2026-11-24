from common import (
    AABB,
    ALIGNMENTS,
    by2,
    mlget as _,
    MurMur,
    RectSpring,
    POLY_BASES,
)
from graphics import (
    ColorGenerator,
    HSL_DST_SQ,
    RGB_DST_SQ,
)
from widgets import (
    AutoVarTreeview,
    Spot,
    SpotImageCache,
)

from pickle import (
    loads,
    dumps,
)
from six.moves.tkinter import (
    BOTH,
    Canvas,
    END,
    Tk,
)


def main():
    root = Tk()
    root.title("Spot Examples")

    c = Canvas(root,
        background = "#FFFFFF",
    )
    c.pack(fill = BOTH, expand = True)

    SCALE = 10.
    PADDING = 30.

    step = SCALE + PADDING
    cg0 = ColorGenerator(MurMur(), metric = RGB_DST_SQ)
    cg1 = ColorGenerator(MurMur(), metric = HSL_DST_SQ)

    cgen = RectSpring(step,
        x = 300, y = 200,
        w = step * 5,
        h = step * 2,
    )
    px, py = next(cgen)

    spots = []
    append = spots.append

    line = c.create_line
    lower = c.lower
    for i, base in enumerate(POLY_BASES):
        for a in ALIGNMENTS:
            x, y = next(cgen)
            lower(line((px, py, x, y),
                fill = "#DDDDDD",
                width = 6,
            ))
            px, py = x, y
            append(Spot(
                base = base,
                align = a,
                offset = (x, y),
                fill = "#%02X%02X%02X" % (next(cg1 if (i & 1) else cg0)),
                canvas = c,
            ))
            line((x - 10, y, x + 10, y))
            line((x, y - 10, x, y + 10))
        cgen = loads(dumps(cgen))

    b = AABB(by2(c.bbox(*c.find_all())))
    w, h = b.get_size()
    w += PADDING * 2
    h += PADDING * 2

    c.configure(width = int(w), height = int(h))
    c.scan_mark(int(b[0] - PADDING), int(b[1] - PADDING))
    c.scan_dragto(0, 0, 1)

    tv = AutoVarTreeview(root,
        columns = [
            "q",
        ],
    )
    tv.heading("#0", text = _("Spots"))
    tv.heading("q", text = _("Quantity"))
    tv.pack(fill = BOTH, expand = True)

    sic = SpotImageCache()
    spots_in_row = 1
    row_spots = []
    add_spot = row_spots.append
    row_height = int(SCALE * 2)

    for spot in spots:
        add_spot(spot)
        if len(row_spots) != spots_in_row:
            continue
        tv.insert("", END,
            image = sic(tuple(row_spots), row_height),
            text = "|",
            values = [
                spots_in_row,
            ],
        )
        row_spots *= 0
        spots_in_row += 1

    tv.adjust_widths()
    root.mainloop()

if __name__ == "__main__":
    exit(main() or 0)
