__all__ = [
    "re_geometry"
  , "tokenize_tk_geometry"
  , "parse_tk_geometry"
  , "apply_tk_geometry"
  , "centrify_tk_window"
  , "TkGeometryHelper"
]

from re import (
    compile
)


re_geometry = compile("(\d+)x(\d+)\+(-?\d+)\+(-?\d+)")


def tokenize_tk_geometry(geom_str):
    mi = re_geometry.match(geom_str)
    return mi.groups()

def parse_tk_geometry(geom_str):
    return tuple(map(int, tokenize_tk_geometry(geom_str)))

# Note, the method is guaranteed to accept 1-4 positional arguments too.
def apply_tk_geometry(window, width = None, height = None, x = None, y = None):
    cur_width, cur_height, cur_x, cur_y = parse_tk_geometry(window.geometry())
    if width is not None:
        cur_width = width
    if height is not None:
        cur_height = height
    if x is not None:
        cur_x = x
    if y is not None:
        cur_y = y
    window.geometry("%sx%s+%s+%s" % (cur_width, cur_height, cur_x, cur_y))


def centrify_tk_window(static, moved):
    w, h, x, y = parse_tk_geometry(static.geometry())
    midx = x + w // 2
    midy = y + h // 2

    w, h = parse_tk_geometry(moved.geometry())[:2]
    x = midx - w // 2
    y = midy - h // 2

    apply_tk_geometry(moved, x = x, y = y)


class TkGeometryHelper(): # Tk classes are not `object`s: don't change it
    "Inheritance extension for a Tk subclass"

    def get_geometry_int(self):
        return parse_tk_geometry(self.geometry())

    def get_geometry(self):
        return tokenize_tk_geometry(self.geometry())

    # Note, the method is guaranteed to accept 1-4 positional arguments too.
    def set_geometry(self, width = None, height = None, x = None, y = None):
        apply_tk_geometry(self, width, height, x, y)

    def set_geometry_delayed(self, *a, **kw):
        """ Just after creation a window has geometry 1x1+0+0. I.e. it has not
been configured by a system window manager yet (which normally displaces the
window in a "smart" way). Hence, to set only width and/or height keeping
the displacement, a delay is required.
        """
        delay = kw.pop("delay", 100)
        self.after(delay, lambda: self.set_geometry(*a, **kw))
