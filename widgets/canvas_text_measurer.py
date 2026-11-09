__all__ = [
    "CanvasTextMeasurer"
]

from common import (
    lazy,
)

from functools import (
    lru_cache,
)
from six.moves.tkinter import (
    Canvas,
)


class CanvasTextMeasurer:
    """ Helper for Tk Widget.
Creates non-mapped Canvas with invisible text to get size of text given.
    """

    @lazy
    def _measure_canvas(self):
        return Canvas(self)

    @lazy
    def _font_measure_tiid(self):
        return self._measure_canvas.create_text(0, 0,
            fill = None,
            outline = None,
        )

    @lru_cache
    def get_text_size(self, text):
        iid = self._font_measure_tiid
        cnv = self._measure_canvas
        cnv.itemconfig(iid, text = text)
        l, t, r, b = cnv.bbox(iid)
        return r - l, b - t
