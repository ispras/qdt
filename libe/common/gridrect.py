__all__ = [
    "GridRect"
]


from .attr_change_notifier import (
    AttributeChangeNotifier,
)
from .events import (
    dismiss,
    listen,
)


class GridRect(AttributeChangeNotifier):
    """ Updates its `coords` with respect to its position (`gcoords`) on
the `g`rid.
    """

    def __init__(self, size, **kw):
        self.size = size
        for nv in kw.items():
            setattr(self, *nv)

    _g = None
    @property
    def g(self):
        return self._g

    @g.setter
    def g(self, g):
        if g is self._g:
            return
        gcoords = self._gcoords
        if self._g is not None:
            dismiss(self._on_grid_resized)
            if gcoords is not None:
                self._g.remove(self)
                del self.coords
        if g is None:
            del self._g
        else:
            self._g = g
            if gcoords is not None:
                g.add(gcoords, self)
                self.coords = g(gcoords)
            listen(g, "resized", self._on_grid_resized)

    _gcoords = None
    @property
    def gcoords(self):
        return self._gcoords

    @gcoords.setter
    def gcoords(self, gcoords):
        if gcoords == self._gcoords:
            return
        g = self._g
        if gcoords is None:
            del self._gcoords
            del self.coords
            if g is not None:
                g.remove(self)
        else:
            if g is not None:
                g.add(gcoords, self)
                self.coords = g(gcoords)
            self._gcoords = gcoords

    def _on_grid_resized(self, axis, coord):
        gcoords = self._gcoords
        if gcoords is None:
            return
        if coord < gcoords[axis]:
            self.coords = self._g(gcoords)
