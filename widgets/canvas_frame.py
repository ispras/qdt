__all__ = [
    "CanvasFrame"
]

from .gui_frame import (
    GUIFrame
)
from six.moves.tkinter import (
    NW
)
from os import (
    name as os_name
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


def translate(e, container):
    "Translates mouse `e`vent relative to `container`."

    w = e.widget
    # container offsets
    cx, cy = 0, 0
    # e.x, e.y. are relative e.widget, but we need x, y relative self
    while w:
        if w is container:
            return True, (e.x + cx), (e.y + cy)
        cx += w.winfo_x()
        cy += w.winfo_y()
        w = w.master
    return False, None, None


# "Alt" keyboard button state checker
# https://stackoverflow.com/questions/19861689/check-if-modifier-key-is-pressed-in-tkinter
if os_name == "nt":
    def alt(e):
        # There is no a confirmation found in a document, but it's observed
        # that under Windows 7 bit 0x20000 is set when `Alt` key (left or
        # right) is being held and bit 0x08 is always set (even when `Alt` is
        # released).
        return e.state & 0x20000
else:
    def alt(e):
        try:
            return e.state & 0x0088
        except TypeError:
            # sometimes e.state is `str`
            return False


# CanvasFrame states, use them with `is` operator only!
resizing = object()
dragging = object()


# `object` is required by `property`
class CanvasFrame(GUIFrame, object):
    """ A container allowing to place widgets onto a `Canvas` with moving and
resizing capabilities.
    """

    def __init__(self, canvas, x, y, *a, **kw):
        canvas_kw = kw.pop("canvas_kw", {})
        kw["padx"] = kw["pady"] = RESIZE_GAP + 2
        GUIFrame.__init__(self, canvas, *a, **kw)

        # resizing and cursor
        self.bind("<Configure>", self.__on_configure, "+")
        # When using non-all binding, <Motion> event is received near padding
        # only. As a result, hint cursor may appear over inner widgets.
        # To prevent this, we binds to all and filter out outer widgets.
        self.bind_all("<Motion>", self.__on_motion, "+")
        self.bind_all("<ButtonPress-1>", self.__down, "+")
        self.bind_all("<ButtonRelease-1>", self.__up, "+")

        self.__state = None
        self.w, self.h = 0, 0
        self.x, self.y = RESIZE_GAP * 2, RESIZE_GAP * 2
        self.__cursor = self.cget("cursor")

        canvas_kw = dict(canvas_kw) # preserve user's `dict`
        canvas_kw["window"] = self
        canvas_kw["anchor"] = NW

        self.id = canvas.create_window(x, y, **canvas_kw)

    def _set_cursor(self, c):
        if self.__cursor != c:
            self.__cursor = c
            self.config(cursor = c)

    cursor = property(fset = _set_cursor)

    def _set_state(self, s):
        self.__state = s
        if s is dragging:
            self.cursor = "fleur"
        else:
            self._update_cursor()

    state = property(fset = _set_state)

    def __down(self, e):
        inner, x, y = translate(e, self)
        if not inner:
            return

        if alt(e):
            self.__offset_x, self.__offset_y = x, y
            self.state = dragging
        elif self.__side:
            self.__offset_x, self.__offset_y = x, y
            self.state = resizing

    def __up(self, _):
        self.state = None

    def __on_configure(self, e):
        self.w, self.h = e.width, e.height
        self._update_cursor()

    def __on_motion(self, e):
        # filter out events for outer widgets
        inner, x, y = translate(e, self)
        if not inner:
            return

        self.x, self.y = x, y

        state = self.__state
        if state is resizing:
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

        elif state is dragging:
            cnv, _id = self.master, self.id
            ox, oy = self.__offset_x, self.__offset_y
            dx, dy = x - ox, y - oy
            curx, cury = cnv.coords(_id)
            cnv.coords(_id, curx + dx, cury + dy)

        self._update_cursor()

    def _update_cursor(self):
        if self.__state is not None:
            # Update neither side nor cursor during drag actions
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

        self.cursor = SIDE_CURSORS[side]
