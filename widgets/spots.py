from common import (
    MurMur,
)

from functools import (
    lru_cache,
)
from itertools import (
    starmap,
)
from math import (
    cos,
    sin,
    pi,
)
from six.moves import (
    zip,
    zip_longest,
)


def rgb(i):
    b = i & 0xFF
    g = (i >> 8) & 0xFF
    r = (i >> 16) & 0xFF
    return r, g, b


pi_3 = pi / 3.0

def rgb_to_hsl(r, g, b):
    r_n, g_n, b_n = r / 255.0, g / 255.0, b / 255.0

    c_max = max(r_n, g_n, b_n)
    c_min = min(r_n, g_n, b_n)
    delta = c_max - c_min

    l = (c_max + c_min) / 2.0

    if delta == 0:
        h = 0.0
        s = 0.0
    else:
        s = delta / (1.0 - abs(2.0 * l - 1.0))
        # zero division <=> l == 0

        if c_max == r_n:
            h = pi_3 * (((g_n - b_n) / delta) % 6.0)
        elif c_max == g_n:
            h = pi_3 * ((b_n - r_n) / delta + 2.0)
        else:  # c_max == b_n
            h = pi_3 * ((r_n - g_n) / delta + 4.0)

    return h, s, l


def RGB_DST_SQ(rgb0, rgb1):
    r0, g0, b0 = rgb0
    r1, g1, b1 = rgb1
    dr, dg, db = r0 - r1, g0 - g1, b0 - b1
    return dr * dr + dg * dg + db * db


def HSL_DST_SQ(rgb0, rgb1):
    h0, s0, l0 = rgb_to_hsl(*rgb0)
    h1, s1, l1 = rgb_to_hsl(*rgb1)
    dh = abs(h1 - h0)
    if dh > pi:
        dh = 2 * pi - dh
    return RGB_DST_SQ((0., s0 * 2.0, l0 * 2.0), (dh, s1 * 2.0, l1 * 2.0))


class ColorGenerator:

    def __init__(self, rng,
        best_of = 10,
        metric = HSL_DST_SQ,
    ):
        self.irng = iter(rng)
        self.generated = set()
        self.range = tuple(range(best_of))
        self.metric = metric

    def __iter__(self):
        return self

    def __next__(self):
        generated = self.generated
        gen = self.irng.__next__

        if not generated:
            ret = rgb(gen())
            generated.add(ret)
            return ret

        metric = self.metric
        candidates = tuple(rgb(gen()) for _ in self.range)

        m_values = []
        append = m_values.append
        for rgb0 in candidates:
            im = starmap(metric, zip_longest([], generated, fillvalue = rgb0))
            min_dst_sq = next(im)
            for v in im:
                if v < min_dst_sq:
                    min_dst_sq = v
            append(min_dst_sq)

        ret = sorted(tuple(zip(m_values, candidates)))[-1][1]
        generated.add(ret)

        return ret


def iter_by2(i, fill = None):
    i = iter(i)
    for x in i:
        try:
            y = next(i)
        except StopIteration:
            y = fill
        yield x, y


def aabb(i):
    i = iter(i)
    l, t = r, b = next(i)
    for x, y in i:
        if x < l:
            l = x
        elif r < x:
            r = x
        if y < t:
            t = y
        elif b < y:
            b = y
    return l, t, r, b


class AABB(tuple):

    def __new__(cls, *args):
        if len(args) == 1:
            args = aabb(args[0])
        return tuple.__new__(cls, args)

    def get_size(self):
        l, t, r, b = self
        return r - l, b - t

    def get_center(self):
        l, t, r, b = self
        return (l + r) / 2, (t + b) / 2

    def get_width(self):
        return self[2] - self[0]

    def get_height(self):
        return self[3] - self[1]


def iter_poly(n, a = pi / -2.0):
    s = pi * 2.0 / n
    for __ in range(n):
        yield cos(a), sin(a)
        a += s


def iter_sub(i, *center):
    for p in i:
        yield tuple((c - d) for (c, d) in zip(p, center))


def iter_add(i, *offset):
    for p in i:
        yield tuple((c + d) for (c, d) in zip(p, offset))


def iter_mul(i, *factors):
    for p in i:
        yield tuple((c * f) for (c, f) in zip(p, factors))

@lru_cache
def gen_poly_base(*a, **kw):
    poly = tuple(iter_poly(*a, **kw))
    b = AABB(poly)
    return tuple(iter_sub(poly, *b.get_center()))


TRIANGLE = (3,)
DIAMOND = (4,)
SQUARE = (4, pi / 4.)
PENTAGON = (5,)
HEXAGON = (6,)
TRIANGLE_TOP = TRIANGLE
TRIANGLE_RIGHT = (3, 0.)
TRIANGLE_LEFT = (3, pi)
TRIANGLE_BOTTOM = (3, pi / 2.0)
HEXAGON_TILE = (6, 0.)

POLY_BASES = (
    TRIANGLE_TOP,
    TRIANGLE_RIGHT,
    TRIANGLE_BOTTOM,
    TRIANGLE_LEFT,
    DIAMOND,
    SQUARE,
    PENTAGON,
    HEXAGON,
    HEXAGON_TILE,
)


def CENTER(p):
    # Base polygons are center-aligned
    return 0,  0

CENTER_CENTER = CENTER

def LEFT_TOP(p):
    b = AABB(p)
    w, h = b.get_size()
    return w / 2, h / 2

def TOP(p):
    b = AABB(p)
    return 0, b.get_height() / 2

CENTER_TOP = TOP

def RIGHT_TOP(p):
    b = AABB(p)
    w, h = b.get_size()
    return w / -2, h / 2

def RIGHT(p):
    b = AABB(p)
    return b.get_width() / -2, 0

RIGHT_CENTER = RIGHT

def RIGHT_BOTTOM(p):
    b = AABB(p)
    w, h = b.get_size()
    return w / -2, h / -2

def BOTTOM(p):
    b = AABB(p)
    return 0, b.get_height() / -2

CENTER_BOTTOM = BOTTOM

def LEFT_BOTTOM(p):
    b = AABB(p)
    w, h = b.get_size()
    return w / 2, h / -2

def LEFT(p):
    b = AABB(p)
    return b.get_width() / 2, 0

ALIGNMENTS = (
    LEFT_TOP,      TOP,     RIGHT_TOP,
    LEFT,        CENTER,        RIGHT,
    LEFT_BOTTOM, BOTTOM, RIGHT_BOTTOM,
)

@lru_cache
def gen_poly(p,
    scale = 1.0,
    align = CENTER,
    offset = (0., 0.)
):
    base = gen_poly_base(*p)
    return tuple(
        iter_add(
            iter_mul(
                iter_add(
                    base,
                    *align(base)
                ),
                scale, scale
            ),
            *offset
        )
    )

@lru_cache
def get_color_generator(
    RNGClass = MurMur,
    metric = RGB_DST_SQ,
):
    return ColorGenerator(RNGClass(), metric = metric)



def main():
    from six.moves.tkinter import (
        BOTH,
        Canvas,
        Tk,
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
    x = PADDING
    y = PADDING

    cg0 = ColorGenerator(MurMur(), metric = RGB_DST_SQ)
    cg1 = ColorGenerator(MurMur(), metric = HSL_DST_SQ)

    polygon = c.create_polygon
    line = c.create_line
    for i, base in enumerate(POLY_BASES):
        for a in ALIGNMENTS:
            polygon(
                gen_poly(base,
                    scale = SCALE,
                    align = a,
                    offset = (x, y),
                ),
                fill = "#%02X%02X%02X" % (next(cg1 if (i & 1) else cg0)),
                outline = "#000000",
            )
            line((x - 10, y, x + 10, y))
            line((x, y - 10, x, y + 10))
            x += step
        x = PADDING
        y += step

    b = AABB(iter_by2(c.bbox(*c.find_all())))
    w, h = b.get_size()
    w += PADDING
    h += PADDING

    c.configure(width = int(w), height = int(h))

    root.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
