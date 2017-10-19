from copy import deepcopy as dcp

from math import sqrt

from random import random

class Vector(object):
    def __init__(self, x = 0, y = 0):
        self.x, self.y = x, y

    def Length(self):
        return sqrt(self.x * self.x + self.y * self.y)

    def SetLenght(self, value):
        l = self.Length()

        while l == 0:
            self.x = random() - 0.5
            self.y = random() - 0.5
            l = self.Length()

        scale = float(value) / l
        self.x, self.y = self.x * scale, self.y * scale

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

    def Length(self):
        return self.d.Length()

    def SetLenght(self, value):
        self.d.SetLenght(value)

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

class Polygon(object):
    def __init__(self, points = None, deepcopy = True):
        if not points:
            self.points = [Vector(), Vector(), Vector()]
        else:
            self.points = dcp(points) if deepcopy else points

    def SetPoint(self, v, idx = 0):
        p = self.points[idx]
        p.x, p.y = v.x, v.y

    def SegmentsGenerator(self):
        v0 = self.points[0]
        for p in self.points[1:]:
            s = Segment(
                begin = v0,
                direction = Vector(p.x - v0.x, p.y - v0.y)
            )
            yield s
            v0 = p

        p = self.points[0]
        s = Segment(
            begin = v0,
            direction = Vector(p.x - v0.x, p.y - v0.y)
        )
        yield s

        raise StopIteration()

    def CoordsGenerator(self):
        for p in self.points:
            yield p.x
            yield p.y

    def GenSegments(self):
        return [x for x in self.SegmentsGenerator()]

    def GenCoords(self):
        return [x for x in self.CoordsGenerator()]

    def Crosses(self, segment):
        crosses = []
        for s in self.SegmentsGenerator():
            c = s.Intersects(segment)
            if c:
                crosses.append(c)
        return crosses

def sign(x):
    return 1 if x >= 0 else -1
