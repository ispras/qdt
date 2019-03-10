__all__ = [
    "AutoPanedWindow"
]

from six.moves.tkinter import (
    HORIZONTAL,
    PanedWindow
)
from six.moves import (
    range
)


class AutoPanedWindow(PanedWindow):
    "Automatically resizes panes keeping size ratio."

    def __init__(self, master, *a, **kw):
        PanedWindow.__init__(self, master, *a, **kw)

        # Previous size is updated iff it has been actually accounted.
        # This prevents incorrect pane size aspect keeping during small
        # size changes.
        self._prev_size = 1.

        self.bind("<Configure>", self._on_configure, "+")

    def _on_configure(self, e):
        clen = len(self.panes())
        if not clen:
            return

        prev = self._prev_size
        horiz = self.cget("orient") == HORIZONTAL

        size = float((e.width if horiz else e.height) -
            (clen - 1) * (
                int(str(self.cget("sashwidth"))) +
                2 * int(str(self.cget("sashpad")))
            )
        )

        if size < 2 * clen:
            # No children or new size is too small.
            self._prev_size = size
            return

        self._new_coords = new_coords = []

        if prev < 2 * clen:
            # The widget has been to tight previously
            csize = int(size / clen)
            for i, coord in enumerate(range(csize, int(size - csize), csize)):
                if horiz:
                    new_coords.append((coord, 0))
                else:
                    new_coords.append((0, coord))

            self._prev_size = size
            self.after_idle(self._update_sashes)
        else:
            scale = size / prev
            for i in range(clen - 1):
                x, y = self.sash_coord(i)
                if horiz:
                    new_x = int(x * scale)
                    if abs(new_x - x) < 2:
                        # resizing is too small
                        break
                    new_y = y
                else:
                    new_x = x
                    new_y = int(y * scale)
                    if abs(new_y - y) < 2:
                        # resizing is too small
                        break

                new_coords.append((new_x, new_y))
            else:
                self._prev_size = size
                self.after_idle(self._update_sashes)

    def _update_sashes(self):
        """ Immediate sashes moving during `_on_configure` is buggy. Instead,
move them after a while.
        """
        for i, (x, y) in enumerate(self._new_coords):
            self.sash_place(i, x, y)
