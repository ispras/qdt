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

SIDE_CURSORS = (
    "",                    # no side
    "sb_h_double_arrow",   # left
    "sb_h_double_arrow",   # right
    "",                    # impossible
    "sb_v_double_arrow",   # top
    "top_left_corner",     # top-left
    "top_right_corner",    # top-right
    "",                    # impossible
    "sb_v_double_arrow",   # bottom
    "bottom_left_corner",  # bottom-left
    "bottom_right_corner", # bottom-right
)


class CanvasFrame(GUIFrame):
    """ A container allowing to place widgets onto a `Canvas` with moving and
resizing capabilities.
    """

    def __init__(self, canvas, x, y, *a, **kw):
        kw["padx"] = kw["pady"] = RESIZE_GAP + 2
        GUIFrame.__init__(self, canvas, *a, **kw)

        # resizing and cursor
        self.bind("<Configure>", self.__on_configure, "+")
        # When using non-all binding, <Motion> event is received near padding
        # only. As a result, hint cursor may appear over inner widgets.
        # To prevent this, we binds to all and filter out outer widgets.
        self.bind_all("<Motion>", self.__on_motion, "+")
        self.bind("<ButtonPress-1>", self.__down, "+")
        self.bind("<ButtonRelease-1>", self.__up, "+")

        self.dragging = False
        self.w, self.h = 0, 0
        self.x, self.y = RESIZE_GAP * 2, RESIZE_GAP * 2
        self.cursor = self.cget("cursor")

        self.id = canvas.create_window(x, y, window = self, anchor = NW)

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
        # filter out events for outer widgets
        w = e.widget
        # self offsets
        # e.x, e.y. are relative e.widget, but we need x, y relative self
        sx, sy = 0, 0
        while w:
            if w is self:
                break
            sx += w.winfo_x()
            sy += w.winfo_y()
            w = w.master
        else:
            # outer widget
            return

        self.x, self.y = x, y = e.x + sx, e.y + sy

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

        side_cursor = SIDE_CURSORS[side]
        if self.cursor != side_cursor:
            self.cursor = side_cursor
            self.config(cursor = side_cursor)
