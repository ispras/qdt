__all__ = [
    "Grid"
]

from .attr_change_notifier import (
    AttributeChangeNotifier,
)
from .bisectmap import (
    BisectMap,
)
from common.lazy import (
    lazy,
)
from .events import (
    listen,
    dismiss,
    notify,
)

from itertools import (
    count,
)
from six.moves import (
    zip as izip,
)


class _GridAxisSliceSlot(object):

    __slice__ = ("size", "o", "slices",)

    def __init__(self, o, dim):
        self.o = o
        self.size = (0,) * dim
        self.slices = [None] * dim

    def __call__(self, n, v):
        if n != "size":
            return
        self._set_size(v)

    def _set_size(self, v):
        for slc, sc, vc in izip(self.slices, self.size, v):
            if sc == vc:
                # size along the axis is not changed
                continue

            nsc = slc[sc] - 1
            if nsc:
                slc[sc] = nsc
            else:
                del slc[sc]

            nvc = slc[vc] + 1
            slc[vc] = nvc

            # `if nvc == 1` then `vc` is new value in sizes.
            # And, `if vc == sizes.max()` then slice is either inflatred
            # (`if sc < vc`) or deflated (`if vc < sc`).
            # `if nsc == 0` then there are no more `sc`-sized values
            # in the slice.
            # And, `if vc < sc` then slice can be defalted.
            # And, `if sizes.max() < sc` then `sc` was previous maxsimum.
            # So, the slice is definetly deflated.

            if (
                (nvc == 1 and slc.max() == vc)
            or  ((not nsc) and slc.max() < sc)
            ):
                slc.axis._invalidate(slc.coord)

        self.size = v


def _zero(_):
    return 0


class _GridSlice(BisectMap):

    __slots__ = ("axis", "coord",)

    def __init__(self, axis, coord):
        super(_GridSlice, self).__init__(factory = _zero)
        self.axis = axis
        self.coord = coord


class _GridAxis(AttributeChangeNotifier):

    def __init__(self, g, i):
        self.g = g
        self.i = i
        # Key is coordinate along the axis.
        self.slices = BisectMap(self._gen_slice)

    def _gen_slice(self, coord):
        # Value is amount of slots with corresponding `size` (key)
        # along the `axis`.
        return _GridSlice(self, coord)

    def iter_offs(self):
        ni = -1
        off = 0
        for i, s in self.slices.items():
            while ni < i:
                yield off
                ni += 1
            if s:
                off += s.max()
        yield off

    def _invalidate(self, coord):
        del self.offs
        notify(self.g, "resized",
            # axis (coordinate) index
            self.i,
            # all objects which coords[i] > coord are considered moved
            coord,
        )

    @lazy
    def offs(self):
        return tuple(self.iter_offs())


class Grid(object):

    def __init__(self, dimensions = 2):
        self._axises = tuple(_GridAxis(self, i) for i in range(dimensions))
        self._zeros = (0,) * dimensions
        self._o2s = {}

    def add(self, coords, o):
        axises = self._axises
        o2s = self._o2s

        slt = o2s.get(o)
        if slt is None:
            o2s[o] = slt = _GridAxisSliceSlot(o, len(axises))
            listen(o, "setattr", slt)
        else:
            # `o`bject is removed from previous slot.
            # So, slot size is considered to become 0.
            slt._set_size(self._zeros)

        for i, c, a in zip(count(), coords, axises):
            slc = a.slices[c]
            slt.slices[i] = slc

        slt._set_size(o.size)

    def remove(self, o):
        slt = self._o2s.pop(o)
        dismiss(slt)
        slt._set_size(self._zeros)

    def iter_cell_offs(self, coords):
        for i, a in zip(coords, self._axises):
            yield a.offs[i]

    def __call__(self, coords):
        return tuple(self.iter_cell_offs(coords))
