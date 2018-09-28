__all__ = [
    "CanvasFrame"
]

from .gui_frame import (
    GUIFrame
)
from six.moves.tkinter import (
    NW
)

RESIZE_GAP = 4
DOUBLE_GAP = RESIZE_GAP << 1


class CanvasFrame(GUIFrame):
    """ A container allowing to place widgets onto a `Canvas` with moving and
    resizing capabilities.

    XXX: Because of unknown reason <Motion> event is received near padding
    only. As a result, hint cursor may appear over inner widgets.
    """

    def __init__(self, canvas, x, y, *a, **kw):
        kw["padx"] = kw["pady"] = RESIZE_GAP + 2
        GUIFrame.__init__(self, canvas, *a, **kw)

        # resizing and cursor
        self.bind("<Configure>", self.__on_configure, "+")
        self.bind("<Motion>", self.__on_motion, "+")
        self.bind("<ButtonPress-1>", self.__down, "+")
        self.bind("<ButtonRelease-1>", self.__up, "+")

        self.dragging = False
        self.w, self.h = 0, 0
        self.x, self.y = RESIZE_GAP * 2, RESIZE_GAP * 2
        self.cursor = self.cget("cursor")

        self.id = _id = canvas.create_window(x, y, window = self, anchor = NW)

    def __down(self, e):
        side = self.__side
        if side:
            self.__offset_x, self.__offset_y = e.x, e.y
            self.dragging = True

    def __up(self, _):
        self.dragging = False

    def __on_configure(self, e):
        self.w, self.h = e.width, e.height
        self._update_cursor()

    def __on_motion(self, e):
        if e.widget is not self:
            return

        self.x, self.y = x, y = e.x, e.y

        if self.dragging:
            cnv = self.master

            ox, oy = self.__offset_x, self.__offset_y

            _id = self.id
            side = self.__side

            if side & 2: # right
                w = self.w + x - ox
                if w > DOUBLE_GAP:
                    cnv.itemconfig(_id, width = w)
                    self.__offset_x = x

            elif side & 1: # left
                dx = x - ox
                w = self.w - dx

                if w > DOUBLE_GAP:
                    curx, cury = cnv.coords(_id)
                    cnv.coords(_id, curx + dx, cury)
                    cnv.itemconfig(_id, width = w)
                    self.__offset_x = x - dx

            if side & 8: # bottom
                h = self.h + y - oy
                if h > DOUBLE_GAP:
                    cnv.itemconfig(_id, height = h)
                    self.__offset_y = y

            elif side & 4: # top
                dy = y - oy
                h = self.h - dy

                if h > DOUBLE_GAP:
                    curx, cury = cnv.coords(_id)
                    cnv.coords(_id, curx, cury + dy)
                    cnv.itemconfig(_id, height = h)
                    self.__offset_y = y - dy

        self._update_cursor()

    def _update_cursor(self):
        if self.dragging:
            # Update neither side nor cursor during dragging
            return

        x, y = self.x, self.y

        if x <= RESIZE_GAP:
            side = 1
        elif self.w - x <= RESIZE_GAP:
            side = 2
        else:
            side = 0

        if y <= RESIZE_GAP:
            side |= 4
        elif self.h - y <= RESIZE_GAP:
            side |= 8

        self.__side = side

        hor = side & 3
        vert = side & 12

        if hor and vert:
            if self.cursor != "sizing":
                self.cursor = "sizing"
                self.config(cursor = "sizing")
        elif hor:
            if self.cursor != "sb_h_double_arrow":
                self.cursor = "sb_h_double_arrow"
                self.config(cursor = "sb_h_double_arrow")
        elif vert:
            if self.cursor != "sb_v_double_arrow":
                self.cursor = "sb_v_double_arrow"
                self.config(cursor = "sb_v_double_arrow")
        else:
            if self.cursor != "":
                self.cursor = ""
                self.config(cursor = "")
