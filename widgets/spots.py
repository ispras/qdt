__all__ = [
    "Spot"
  , "rasterize_spots_row"
      , "SpotImageCache"
]

from .ppm import (
    gen_ppm_photo_image,
)

from common import (
    CENTER,
    gen_poly,
    HEXAGON,
    KWInit,
    LEFT_TOP,
    ready,
)
from graphics import (
    blit,
    get_color_generator,
    PyFrameBuffer,
    PyFBDrawer,
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


def rasterize_spots_row(spots,
    height = 20,
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


class SpotImageCache:

    def __init__(self):
        self.settings2image = {}

    def __call__(self, *a, **kw):
        key = a + tuple(sorted(kw.items()))
        try:
            img = self.settings2image[key]
        except KeyError:
            buf, w, __ = rasterize_spots_row(*a, **kw)
            img = gen_ppm_photo_image(buf, w)
            # Reference to generated PhotoImage must not be garbage collected
            # while it's used in a Tk Widget.
            self.settings2image[key] = img
        return img

    def forget(self, spots):
        """ forgets all images given `spots` have been used for
        """
        s2i = self.settings2image
        pop = s2i.pop
        keys = tuple(s2i.keys())
        for spot in spots:
            for key in keys:
                try:
                    key_spots = key[0]
                except IndexError:
                    for n, v in key:
                        if n == "spots":
                            key_spots = v
                            break
                    else:
                        raise AssertionError(
                "`rasterize_spots_row` first argument must be `spots`"
                        )
                if spot in key_spots:
                    pop(key, None)
