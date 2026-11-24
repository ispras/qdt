from common import (
    AABB,
    ALIGNMENTS,
    by2,
    CENTER,
    gen_poly,
    HEXAGON,
    KWInit,
    LEFT_TOP,
    MurMur,
    POLY_BASES,
    ready,
)
from graphics import (
    blit,
    ColorGenerator,
    get_color_generator,
    HSL_DST_SQ,
    PyFrameBuffer,
    PyFBDrawer,
    RGB_DST_SQ,
)


class Spot(KWInit):

    def __kwinit__(self):
        try:
            self.fill
        except AttributeError:
            self.fill = "#%02X%02X%02X" % next(get_color_generator())
        try:
            self.outline
        except AttributeError:
            self.outline = "black"
        try:
            self.align
        except AttributeError:
            self.align = CENTER
        try:
            self.base
        except AttributeError:
            self.base = HEXAGON
        try:
            self.scale
        except AttributeError:
            self.scale = 10.0
        try:
            self.offset
        except AttributeError:
            self.offset = (0, 0)

    @ready
    def iid(self, ready):
        if ready:
            return self._canvas.create_polygon(self._coords,
                fill = self._fill,
                outline = self._outline,
            )
        else:
            self._canvas.delete(self.iid)

    canvas = iid.bit()
    fill = iid.bit()
    outline = iid.bit()
    _coords = iid.bit()

    @ready
    def coords(self, ready):
        if ready:
            return gen_poly(self._base,
                scale = self._scale,
                align = self._align,
                offset = self._offset,
            )

    base = coords.bit()
    scale = coords.bit()
    align = coords.bit()
    offset = coords.bit()

    def get_fill_rgb(self):
        c = self.fill[1:]
        return (
            int(c[:2], base = 16),
            int(c[2:4], base = 16),
            int(c[4:], base = 16)
        )


def rasterize_spots_row(spots, height,
    spacing = 0.1,
    interval = None,
    background = (255, 255, 255),
):
    if not isinstance(spacing, int):
        spacing = int(height * spacing)
    if interval is None:
        interval = spacing
    if not isinstance(interval, int):
        interval = int(height * interval)

    spot_size = height - (spacing << 1)
    spot_size_2 = spot_size >> 1
    n_spots = len(spots)

    # Shading a big buffer in Python is too expensive.
    # Draw each spot into its own small frame buffer.
    # Than blit those buffers onto a big result buffer.
    width = 2 * spacing + interval * (n_spots - 1) + spot_size * n_spots
    buf = [background] * (width * height)
    fb = PyFrameBuffer(height, height,
        fill = background,
    )
    d = PyFBDrawer(fb)

    x = spacing
    step = spot_size + interval
    for spot in spots:
        points = gen_poly(
            spot.base,
            scale = spot_size_2,
            align = LEFT_TOP,
        )
        d.color = spot.get_fill_rgb() + (255,)
        d.fill_poly(*points)
        d.color = (0, 0, 0, 255)
        d.poly(*points)
        blit(buf, width, height, fb.fb, height, height, x, spacing)
        x += step
        fb.clear()

    return buf, width, height


def main():
    from common import (
        RectSpring,
    )
    from widgets import (
        gen_ppm_photo_image,
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
    from six.moves.tkinter_ttk import (
        Treeview,
    )

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

    tv = Treeview(root)
    tv.pack(fill = BOTH, expand = True)

    imgs = []
    append = imgs.append
    spots_in_row = 1
    row_spots = []
    add_spot = row_spots.append
    row_height = int(SCALE * 2)

    for spot in spots:
        add_spot(spot)
        if len(row_spots) != spots_in_row:
            continue
        buf, w, h = rasterize_spots_row(row_spots, row_height)
        row_spots *= 0
        spots_img = gen_ppm_photo_image(buf, w)
        append(spots_img)

        tv.insert("", END,
            image = spots_img,
            text = str(spots_in_row) + " spot(s)",
        )
        spots_in_row += 1

    root.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
