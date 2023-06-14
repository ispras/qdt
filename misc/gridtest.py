from libe.common.attr_change_notifier import (
    AttributeChangeNotifier,
)
from libe.common.events import (
    dismiss,
    listen,
)
from libe.common.grid import (
    Grid,
)

from six.moves.tkinter import (
    BOTH,
    Canvas,
    Tk,
)


class Box(AttributeChangeNotifier):
    _valid = True

    def __init__(self, cnv, size):
        self.cnv = cnv
        self.size = size
        listen(self, "setattr", self._on_setattr)

    def invalidate(self):
        if self._valid:
            self._valid = False
            self.cnv.after(10, self._update)

    def _update(self):
        del self._valid
        if not hasattr(self, "iid"):
            return
        self.cnv.coords(self.iid, *self._coords)

    @property
    def _coords(self):
        x, y = self.xy
        w, h = self.size
        return x + 1, y + 1, x + w + 1, y + h + 1

    def _on_setattr(self, attr, v):
        if attr in ("size", "xy",):
            self.invalidate()

    def hide(self):
        if hasattr(self, "iid"):
            self.cnv.delete(self.iid)
            del self.iid

    def show(self):
        if hasattr(self, "iid"):
            return
        self.iid = self.cnv.create_rectangle(*self._coords)

    _ij = None
    @property
    def ij(self):
        return self._ij

    @ij.setter
    def ij(self, ij):
        if ij == self._ij:
            return
        self._ij = ij
        if self._g is not None:
            if ij is None:
                self._remove_from_g()
            else:
                self._add_to_g()

    _g = None
    @property
    def g(self):
        return self._g

    @g.setter
    def g(self, g):
        if g is self._g:
            return
        if self._g is not None and self._ij is not None:
            self._remove_from_g()
        self._g = g
        if g is not None and self._ij is not None:
            self._add_to_g()

    def _add_to_g(self):
        self._g.add(self._ij, self)
        listen(self._g, "resized", self._on_grid_resized)
        self.xy = self._g(self._ij)
        self.show()

    def _remove_from_g(self):
        self._g.remove(self)
        dismiss(self._on_grid_resized)
        self.hide()

    def _on_grid_resized(self, axis, coord):
        ij = self._ij
        if ij is None:
            return
        if coord < ij[axis]:
            self.xy = self._g(ij)


def main():
    r = Tk()
    r.title("Grid Test")

    c = Canvas(r,
        bg = "white",
    )
    c.pack(fill = BOTH, expand = True, padx = 10, pady = 10)

    g = Grid()

    boxes = []

    for gx, gy, w, h in [
        (0, 0, 10, 10),
        (0, 2, 10, 10),
        (1, 1, 20, 20),
        (1, 1, 10, 10),
        (2, 2, 30, 30),
        (3, 2, 10, 10),
        (10, 10, 5, 5),
    ]:
        box = Box(c, (w, h))
        box.ij = (gx, gy)
        box.g = g
        boxes.append(box)

    def co_script():
        while True:
            boxes[1].size = 40, 40
            yield
            boxes[1].size = 10, 10
            yield
            boxes[1].size = 0, 0
            yield
            boxes[0].size = 0, 0
            yield
            boxes[0].size = 10, 10
            yield
            boxes[1].size = 10, 10
            yield
            boxes[3].size = 5, 5
            yield
            boxes[3].size = 30, 30
            yield
            boxes[3].size = 10, 10
            yield
            boxes[4].g = None
            yield
            boxes[4].g = g
            yield
            boxes[4].ij = (2, 0)
            yield
            boxes[4].ij = (2, 2)
            yield

    script = co_script()
    def script_step(_):
        try:
            next(script)
        except StopIteration:
            return

    r.bind("<Return>", script_step)
    r.bind("<KP_Enter>", script_step)

    r.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
