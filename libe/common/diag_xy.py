__all__ = [
    "iter_diag_xy"
  , "StringMesh"
]

from six.moves import (
    zip,
)


def iter_diag_xy():
    x = 0
    y = 0
    yield 0, 0  # (x, y)

    while True:
        x += 1
        yield x, y

        while x > 0:
            x -= 1
            y += 1
            yield x, y

        y += 1
        yield x, y

        while y > 0:
            y -= 1
            x += 1
            yield x, y


class StringMesh(list):
    """
>>> m = StringMesh(fill = '.')
>>> m[0, 0] = 'a'
>>> m[1, 1] = 'b'
>>> m[-1, -1] = 'z'
>>> print(m)
a.........
.b........
..........
..........
..........
..........
..........
..........
..........
.........z
>>> m = StringMesh(5, 5, fill = "...")
>>> for i, xy in enumerate(iter_diag_xy()):
...     try:
...         m[xy] = str(i)
...     except IndexError:
...         break
>>> print(m)
  0  1  5  6 14
  2  4  7 13...
  3  8 12......
  9 11.........
 10............
    """


    def __init__(self, w = 10, h = 10, fill = " "):
        super(StringMesh, self).__init__(
            ([fill] * w) for __ in range(h)
        )
        self._max_l = [len(fill)] * w

    def __setitem__(self, xy, v):
        x, y = xy
        self[y][x] = v
        ml = self._max_l
        l = len(v)
        if ml[x] < l:
            ml[x] = l

    def iter_lines(self, sep = ""):
        cfmts = list(map("%%%ds".__mod__, self._max_l))
        for r in self:
            yield sep.join((fmt % c) for (fmt, c) in zip(cfmts, r))

    def __str__(self):
        return "\n".join(self.iter_lines())
