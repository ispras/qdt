from math import (
    sqrt
)

__all__ = [
    "PhObject"
      , "PhBox"
      , "PhCircle"
]

class PhObject(object):
    """ This is a point (x, y) in a 2D Euclidean space. It has velocity
    (vx, vy) and spacing along both X-axis and Y-axis. The spacing is accounted
    during collision detection. The point could be static. While an object is
    static, the physical simulator does not moves it. """
    def __init__(self,
            # "physics" parameters
            x = 200, y = 200,
            vx = 0, vy = 0,
            spacing = 10,
            # the node cannot be moved by engine if static
            static = False
        ):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.spacing = spacing
        self.static = static

    def aabb(self):
        x, y, = self.x, self.y
        return x, y, x + self.width, y + self.height


class PhBox(PhObject):
    """ Axis aligned box or vertical line (width == 0) or horizontal line
    (height == 0). """
    def __init__(self, w = 50, h = 50, **kw):
        PhObject.__init__(self, **kw)
        self.width, self.height = w, h

    def overlaps_box(self, b):
        """ Checks collision with a box. """
        b_spacing = b.spacing
        self_spacing = self.spacing
        if b.x - b_spacing > self.x + self.width + self_spacing:
            return False
        if b.x + b.width + b_spacing < self.x - self_spacing:
            return False
        if b.y - b_spacing > self.y + self.height + self_spacing:
            return False
        if b.y + b.height + b_spacing < self.y - self_spacing:
            return False
        return True

    def touches_hline(self, l):
        """ Checks collision with a horizontal line.
        Spacing of the line is ignored. """
        self_spacing = self.spacing
        if self.y - self_spacing > l.y:
            return False
        if self.y + self.height + self_spacing < l.y:
            return False
        if self.x + self.width + self_spacing < l.x:
            return False
        if self.x - self_spacing > l.x + l.width:
            return False
        return True

    def touches_vline(self, l):
        """ Checks collision with a vertical line.
        Spacing of the line is ignored. """
        self_spacing = self.spacing
        if self.x - self_spacing > l.x:
            return False
        if self.x + self.width + self_spacing < l.x:
            return False
        if self.y - self_spacing > l.y + l.height:
            return False
        if self.y + self.height + self_spacing < l.y:
            return False
        return True

    def crosses_vline(self, l):
        """ Checks collision with a vertical line when self is a horizontal
        line (height == 0). Spacing is ignored for both lines. """
        if self.x > l.x:
            return False
        if self.y < l.y:
            return False
        if self.x + self.width < l.x:
            return False
        if l.y + l.height < self.y:
            return False
        return True

class PhCircle(PhObject):
    """ Circle. Size is given as radius (r). """
    def __init__(self, r = 10, **kw):
        PhObject.__init__(self, **kw)
        self.r = r

    def overlaps_circle(self, c):
        """ Checks collision with a circle. """
        dx = c.x + c.r - (self.x + self.r)
        dy = c.y + c.r - (self.y + self.r)
        return sqrt(dx * dx + dy * dy) \
            < c.r + c.spacing + self.r + self.spacing

    def overlaps_box(self, b):
        """ Checks collision with a box. This circle is accounted as a `PhBox`
        with width == height == r * 2. """
        self_spacing = self.spacing
        b_spacing = b.spacing
        d = self.r * 2
        # it is not a precise check
        if self.x + d + self_spacing < b.x - b_spacing:
            return False
        if self.y + d + self_spacing < b.y - b_spacing:
            return False
        if b.x + b.width + b_spacing < self.x - self_spacing:
            return False
        if b.y + b.height + b_spacing < self.y - self_spacing:
            return False
        return True
