__all__ = [
    "rgb"
  , "rgb_to_hsl"
  , "RGB_DST_SQ"
  , "HSL_DST_SQ"
  , "ColorGenerator"
      , "get_color_generator"
]


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
    pi,
)
from six.moves import (
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


@lru_cache
def get_color_generator(
    RNGClass = MurMur,
    metric = RGB_DST_SQ,
):
    return ColorGenerator(RNGClass(), metric = metric)
