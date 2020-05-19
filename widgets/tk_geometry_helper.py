__all__ = [
    "re_geometry"
  , "tokenize_tk_geometry"
  , "apply_tk_geometry"
  , "TkGeometryHelper"
]

from re import (
    compile
)


re_geometry = compile("(\d+)x(\d+)\+(\d+)\+(\d+)")


def tokenize_tk_geometry(geom_str):
    mi = re_geometry.match(geom_str)
    return mi.groups()

# Note, the method is guaranteed to accept 1-4 positional arguments too.
def apply_tk_geometry(window, width = None, height = None, x = None, y = None):
    cur_width, cur_height, cur_x, cur_y = window.get_geometry()
    if width is not None:
        cur_width = width
    if height is not None:
        cur_height = height
    if x is not None:
        cur_x = x
    if y is not None:
        cur_y = y
    window.geometry("%sx%s+%s+%s" % (cur_width, cur_height, cur_x, cur_y))



class TkGeometryHelper(): # Tk classes are not `object`s: don't change it
    "Inheritance extension for a Tk subclass"

    def get_geometry_int(self):
        return tuple(map(int, self.get_geometry()))

    def get_geometry(self):
        return tokenize_tk_geometry(self.geometry())

    # Note, the method is guaranteed to accept 1-4 positional arguments too.
    def set_geometry(self, width = None, height = None, x = None, y = None):
        apply_tk_geometry(self, width, height, x, y)
