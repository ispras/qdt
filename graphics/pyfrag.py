__all__ = [
    "PyFrameBuffer"
  , "PyFBDrawer"
]

from itertools import (
    count,
)
from math import (
    sqrt,
)


class PyFrameBuffer(object):

    def __init__(self, w, h,
        fill = (0, 0, 0),
    ):
        self._w = w
        self._h = h
        if len(fill) != 3:
            raise ValueError("fill color size %d must be 3" % (len(fill),))
        self._fill = fill
        self.clear()

    def draw_fragments(self, *shaders):
        fb = self.fb
        x = 0
        y = 0
        n = count().__next__
        for y in range(self._h):
            for x in range(self._w):
                i = n()
                r, g, b = fb[i]
                for s in shaders:
                    sr, sg, sb, sa = s(x, y)
                    a = 255 - sa
                    r = (r * a + sr * sa) // 255
                    g = (g * a + sg * sa) // 255
                    b = (b * a + sb * sa) // 255
                fb[i] = (r, g, b)

    def clear(self):
        self.fb = [self._fill] * (self._w * self._h)


def length(x, y):
    return sqrt(x * x + y * y)

def dot(x1, y1, x2, y2):
    return x1 * x2 + y1 * y2

def clamp(x, l, r):
    if x < l:
        return l
    if r < x:
        return r
    return x

def dst2segment(Px, Py, Ax, Ay, Bx, By):
    dx = Bx - Ax
    dy = By - Ay
    AB2 = dx * dx + dy * dy
    if AB2 == 0:
        return length(Px - Ax, Py - Ay)
    t = dot(Px - Ax, Py - Ay, dx, dy) / AB2
    tc = clamp(t, 0., 1.)
    Cx = Ax + dx * tc
    Cy = Ay + dy * tc
    return length(Px - Cx, Py - Cy)

def pointInPoly(x, y, points):
    inside = False
    pPx, pPy = points[-1]
    for p in points:
        Px, Py = p
        if (y < Py) is not (y < pPy):
            if x < (pPx + (y - pPy) * (Px - pPx) / (Py - pPy)):
                inside = not inside
        pPx, pPy = p
    return inside

def step(r, x):
    return r < x

def smoothstep(l, r, x):
    t = clamp((x - l) / (r - l), 0, 1)
    return t * t * (3 - 2 * t)


NOP_COLOR = (0, 0, 0, 0)

class PyFBDrawer(object):

    def __init__(self, fb,
        color = (0, 0, 0, 255),
        linewidth = 1,
        smooth = True,
    ):
        self._fb = fb
        self.color = color
        self.linewidth = linewidth
        self.smooth = smooth

    def segment(self, AxAy_BxBy):
        self._segment = AxAy_BxBy
        self._fb.draw_fragments(self._segment_shader)

    def _segment_shader(self, x, y):
        d = dst2segment(x, y, *self._segment)
        r, g, b, a = self.color
        if self.smooth:
            a = int(a * (1 - smoothstep(0, self.linewidth, d)))
        else:
            a = 0 if step(self.linewidth, d) else a
        return r, g, b, a

    def poly(self, *points):
        self._points = list(points + points[:1])
        self._i = 0
        self._I = len(points)
        self._fb.draw_fragments(*(self._poly_segment_shader,) * len(points))

    def _poly_segment_shader(self, x, y):
        i, I, p = self._i, self._I, self._points
        j = i + 1
        self._segment = p[i] + p[j]
        ret = self._segment_shader(x, y)
        if j == I:
            self._i = 0
        else:
            self._i = j
        return ret

    def fill_poly(self, *points):
        self._points = points
        self._fb.draw_fragments(self._fill_poly_shader)

    def _fill_poly_shader(self, x, y):
        if pointInPoly(x, y, self._points):
            return self.color
        else:
            return NOP_COLOR
