class Vector(object):
    def __init__(self, x = 0, y = 0):
        self.x, self.y = x, y

    def Cross(self, p):
        return self.x * p.y - self.y * p.x

class Segment(Vector):
    def __init__(self, begin = None, direction = None):
        if not begin:
            begin = Vector()
        if not direction:
            direction = Vector()
        self.x, self.y = begin.x, begin.y
        self.d = Vector(direction.x, direction.y)

    def Intersects(self, v):
        # based on http://stackoverflow.com/questions/563198/how-do-you-detect-where-two-line-segments-intersect
        cross = self.d.Cross(v.d)

        if cross == 0:
            # parallel
            return None

        dst = Vector(v.x - self.x, v.y - self.y)
        tmp = dst.Cross(v.d)

        t = float(tmp) / float(cross)

        if t < 0 or t > 1:
            return None

        tmp = dst.Cross(self.d)
        u = float(tmp) / float(cross)

        if u < 0 or u > 1:
            return None

        return Vector(self.x + self.d.x * t, self.y + self.d.y * t)

    def SetPoint(self, v, idx = 0):
        if idx == 0:
            oldx, oldy = self.x + self.d.x, self.x + self.d.y
            self.x = v.x
            self.y = v.y
            self.d.x, self.d.y = oldx - self.x, oldy- self.y
        elif idx == 1:
            self.d.x, self.d.y = v.x - self.x, v.y - self.y
        else:
            raise IndexError()

