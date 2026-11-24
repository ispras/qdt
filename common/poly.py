""" Polygon generation helpers
"""

# no __all__
# Without it all non-`_`-refixed names will be exported

from .mechanics import (
    AABB,
)

from functools import (
    lru_cache as _lru_cache,
)
from math import (
    cos as _cos,
    pi as _pi,
    sin as _sin,
)
from six.moves import (
    zip as _zip,
)


def iter_poly(n, a = _pi / -2.0):
    s = _pi * 2.0 / n
    for __ in range(n):
        yield _cos(a), _sin(a)
        a += s


def iter_sub(i, *center):
    for p in i:
        yield tuple((c - d) for (c, d) in _zip(p, center))


def iter_add(i, *offset):
    for p in i:
        yield tuple((c + d) for (c, d) in _zip(p, offset))


def iter_mul(i, *factors):
    for p in i:
        yield tuple((c * f) for (c, f) in _zip(p, factors))

@_lru_cache
def gen_poly_base(*a, **kw):
    poly = tuple(iter_poly(*a, **kw))
    b = AABB(poly)
    return tuple(iter_sub(poly, *b.get_center()))


TRIANGLE = (3,)
DIAMOND = (4,)
SQUARE = (4, _pi / 4.)
PENTAGON = (5,)
HEXAGON = (6,)
TRIANGLE_TOP = TRIANGLE
TRIANGLE_RIGHT = (3, 0.)
TRIANGLE_LEFT = (3, _pi)
TRIANGLE_BOTTOM = (3, _pi / 2.0)
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

@_lru_cache
def gen_poly_at_O(p,
    scale = 1.0,
    align = CENTER,
):
    base = gen_poly_base(*p)
    return tuple(
        iter_mul(
            iter_add(
                base,
                *align(base)
            ),
            scale, scale
        )
    )

@_lru_cache
def gen_poly(p,
    offset = (0., 0.),
    **kw
):
    return tuple(
        iter_add(
            gen_poly_at_O(p, **kw),
            *offset
        )
    )
