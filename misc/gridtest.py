from libe.common.events import (
    listen,
)
from libe.common.grid import (
    Grid,
)
from libe.common.gridrect import (
    GridRect,
)

from six.moves.tkinter import (
    BOTH,
    Canvas,
    Tk,
)


class Box(GridRect):
    _valid = True

    def __init__(self, cnv, size):
        super(Box, self).__init__(size)
        self.cnv = cnv
        listen(self, "setattr", self._on_changeattr)
        listen(self, "delattr", self._on_changeattr)

    def invalidate(self):
        if self._valid:
            self._valid = False
            self.cnv.after(10, self._update)

    def _update(self):
        del self._valid

        cnv = self.cnv

        try:
            x, y = self.coords
        except AttributeError:
            try:
                cnv.delete(self._iid)
                del self._iid
            except AttributeError:
                pass
        else:
            w, h = self.size
            ccoords = x + 1, y + 1, x + w + 1, y + h + 1
            try:
                cnv.coords(self._iid, *ccoords)
            except AttributeError:  # _iid
                self._iid = cnv.create_rectangle(*ccoords)

    def _on_changeattr(self, attr, *__):
        if attr in ("size", "coords",):
            self.invalidate()


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
        box.gcoords = (gx, gy)
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
            boxes[4].gcoords = (2, 0)
            yield
            boxes[4].gcoords = (2, 2)
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
