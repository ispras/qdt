#!/usr/bin/python2

from Tkinter import *
from phy import *
from widgets import *

class CrossTest(CanvasDnD):
    def __init__(self, master):
        CanvasDnD.__init__(self, master)

        self.v1_0 = self.canvas.create_rectangle(
            100, 100,
            125, 125,
            fill = "red",
            tags = "DnD"
        )

        self.v1_1 = self.canvas.create_rectangle(
            100, 200,
            125, 225,
            fill = "green",
            tags = "DnD"
        )

        self.v2_0 = self.canvas.create_rectangle(
            200, 100,
            225, 125,
            fill = "blue",
            tags = "DnD"
        )

        self.v2_1 = self.canvas.create_rectangle(
            200, 200,
            225, 225,
            fill = "brown",
            tags = "DnD"
        )

        self.v1 = self.canvas.create_line(
            0, 0, 0, 0,
            fill = "orange"
        )

        self.v2 = self.canvas.create_line(
            0, 0, 0, 0
        )

        self.inter = None

        self.bind('<<DnDMoved>>', self.dnd_moved)

        self.update()

    def update(self):
        p1_0 = self.canvas.coords(self.v1_0)[:2]
        p1_1 = self.canvas.coords(self.v1_1)[:2]

        v1 = Segment(
            begin = Vector(p1_0[0] + 12.5, p1_0[1] + 12.5),
            direction = Vector(
                p1_1[0] - p1_0[0], p1_1[1] - p1_0[1],
            )
        )

        p2_0 = self.canvas.coords(self.v2_0)[:2]
        p2_1 = self.canvas.coords(self.v2_1)[:2]

        v2 = Segment(
            begin = Vector(p2_0[0] + 12.5, p2_0[1] + 12.5),
            direction = Vector(
                p2_1[0] - p2_0[0], p2_1[1] - p2_0[1],
            )
        )

        apply(self.canvas.coords, [self.v1] + \
            [v1.x, v1.y, v1.x + v1.d.x, v1.y + v1.d.y])

        apply(self.canvas.coords, [self.v2] + \
            [v2.x, v2.y, v2.x + v2.d.x, v2.y + v2.d.y])

        inter_point = v1.Intersects(v2)

        if inter_point:
            if not self.inter:
                self.inter = self.canvas.create_oval(0, 0, 0, 0)

            apply(self.canvas.coords, [self.inter] + \
                [inter_point.x - 10, inter_point.y - 10,
                 inter_point.x + 10, inter_point.y + 10]
            )
        else:
            if self.inter:
                self.canvas.delete(self.inter)
                self.inter = None

    def dnd_moved(self, event):
        self.update()

def main():
    root = Tk()
    root.title("Physic test")

    root.grid()
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)
    root.geometry("500x500")

    cnv = CrossTest(root)
    cnv.grid(column = 0, row = 0, sticky = "NEWS")

    root.mainloop()

if __name__ == '__main__':
    main()