#!/usr/bin/env python

from common import (
    Polygon,
    Segment,
    Vector,
)
from widgets import (
    CanvasDnD,
)

from six.moves.tkinter import (
    Tk,
)


class CanvasPolygon(Polygon):

    def __init__(self, canvas, *points, **kwargs):
        pts = []
        i = iter(points)
        while True:
            try:
                pts.append(Vector(next(i), next(i)))
            except StopIteration:
                break
        points = pts

        Polygon.__init__(self, points, deepcopy = False)
        self.c = canvas
        self.p = self.c.create_polygon(
            tuple(self.GenCoords()),
            **kwargs
        )

    def update(self):
        self.c.coords(*([self.p] + self.GenCoords()))


class CanvasSegment(Segment):

    def __init__(self, canvas, begin = None, direction = None, **kwargs):
        Segment.__init__(self, begin, direction)
        self.c = canvas
        self.l = self.c.create_line(
            self.x, self.y, self.x + self.d.x, self.y + self.d.y,
            **kwargs
        )

    def update(self):
        self.c.coords(*([self.l] + \
            [self.x, self.y, self.x + self.d.x, self.y + self.d.y])
        )


class CrossTest(CanvasDnD):

    def __init__(self, master):
        CanvasDnD.__init__(self, master)

        self.polygons = []
        self.segments = []
        self.crosses = []
        self.drag_points = {}
        self.dp_w2 = 10

        self.segments.extend([
            CanvasSegment(self,
                Vector(100, 100),
                Vector(0, 100),
                fill = "red"
            ),
            CanvasSegment(self,
                Vector(200, 100),
                Vector(0, 100),
                fill = "green"
            ),
        ])
        self.polygons.extend([
            CanvasPolygon(self,
                300, 300,
                400, 300,
                400, 400,
                300, 400,
                fill = "",
                outline = "black"
            )
        ])

        self.bind('<<DnDMoved>>', self.dnd_moved)

        self.create_drags()
        self.refresh()

    def create_drags(self):
        for p in self.polygons:
            for i, v in enumerate(p.points):
                _id = self.create_rectangle(
                    v.x - self.dp_w2, v.y - self.dp_w2,
                    v.x + self.dp_w2, v.y + self.dp_w2,
                    fill = "white",
                    tags = "DnD"
                )
                self.drag_points[_id] = p, i

        for s in self.segments:
            _id = self.create_rectangle(
                s.x - self.dp_w2, s.y - self.dp_w2,
                s.x + self.dp_w2, s.y + self.dp_w2,
                fill = "white",
                tags = "DnD"
            )
            self.drag_points[_id] = s, 0
            _id = self.create_rectangle(
                s.x + s.d.x - self.dp_w2, s.y + s.d.y - self.dp_w2,
                s.x + s.d.x + self.dp_w2, s.y + s.d.y + self.dp_w2,
                fill = "white",
                tags = "DnD"
            )
            self.drag_points[_id] = s, 1

    def refresh(self):
        for i in self.segments + self.polygons:
            i.update()

        for c in self.crosses:
            self.delete(c)

        crosses = []
        for p in self.polygons:
            for s in self.segments:
                crosses.extend(p.Crosses(s))

        for idx, s in enumerate(self.segments[:-1]):
            for s1 in self.segments[idx + 1:]:
                c = s.Intersects(s1)
                if c:
                    crosses.append(c)

        for c in crosses:
            _id = self.create_oval(
                c.x - 10, c.y - 10,
                c.x + 10, c.y + 10
            )
            self.crosses.append(_id)

    def dnd_moved(self, event):
        for dp, do in self.drag_points.items():
            coords = self.coords(dp)[:2]
            do[0].SetPoint(
                Vector(coords[0] + self.dp_w2, coords[1] + self.dp_w2),
                do[1]
            )

        self.refresh()


def main():
    root = Tk()
    root.title("Physic test")

    root.grid()
    root.grid_columnconfigure(0, weight = 1)
    root.grid_rowconfigure(0, weight = 1)
    root.geometry("500x500")

    cnv = CrossTest(root)
    cnv.grid(column = 0, row = 0, sticky = "NEWS")

    root.mainloop()

if __name__ == '__main__':
    main()
