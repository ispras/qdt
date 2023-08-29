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
        if self._g is not None and self._gcoords is not None:
            self._remove_from_g()
        if g is None:
            del self._g
        else:
            self._g = g
            if self._gcoords is not None:
                self._add_to_g()

    _gcoords = None
    @property
    def gcoords(self):
        return self._gcoords

    @gcoords.setter
    def gcoords(self, gcoords):
        if gcoords == self._gcoords:
            return

        if self._g is not None:
            self._remove_from_g()

        if gcoords is None:
            del self._gcoords
        else:
            self._gcoords = gcoords
            if self._g is not None:
                self._add_to_g()

    def _add_to_g(self):
        g = self._g
        gcoords = self._gcoords
        g.add(gcoords, self)
        listen(g, "resized", self._on_grid_resized)
        self.coords = g(gcoords)

    def _on_grid_resized(self, axis, coord):
        gcoords = self._gcoords
        if gcoords is None:
            return
        if coord < gcoords[axis]:
            self.coords = self._g(gcoords)

    def _remove_from_g(self):
        self._g.remove(self)
        dismiss(self._on_grid_resized)
        del self.coords
