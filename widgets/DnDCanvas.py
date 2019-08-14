#!/usr/bin/python2
# based on http://code.activestate.com/lists/python-list/281562/

__all__ = [
    "CanvasDnD"
  , "dragging"
]

from .gui_frame import (
    GUIFrame
)
from six.moves import (
    range as xrange
)
from six.moves.tkinter import (
    IntVar,
    Canvas,
    RIDGE,
    BOTH
)


# CanvasDnD states, use them with `is` operator only
dragging = object()


class CanvasDnD(GUIFrame):
    def __init__(self, master,
            id_priority_sort_function = lambda ids : ids,
            mesh_step = 20
        ):

        GUIFrame.__init__ (self, master)
        self.canvas = cnv = Canvas (self,
            width = 100, # default width
            height = 100, # default height
            relief = RIDGE,
            background = "white",
            borderwidth = 1
        )

        cnv.pack(expand = 1, fill = BOTH)

        self.align = False
        self.mesh_step = IntVar(value = mesh_step)
        self._state = None
        self.off = None
        cnv.bind("<ButtonPress-1>", self.down, "+")
        cnv.bind("<ButtonRelease-1>", self.up, "+")
        cnv.bind("<Motion>", self.motion, "+")

        self.id_priority_sort_function = id_priority_sort_function

    # backward compatibility properties
    @property
    def dragging(self):
        return self._state is dragging

    def down(self, event):
        x, y = event.widget.canvasx(event.x), event.widget.canvasy(event.y)

        touched = self.canvas.find_overlapping(x - 1, y - 1, x + 1, y + 1)
        touched = [ t for t in touched if ("DnD" in self.canvas.gettags(t)) ]

        if not touched:
            return

        touched = self.id_priority_sort_function(touched)
        self.dnd_dragged = touched[0]

        offset = event.widget.coords(self.dnd_dragged)
        self.off = (x - offset[0], y - offset[1])

        #print str((x,y)) + " - " + str(self.off)

        self._state = dragging
        self.event_generate('<<DnDDown>>')

    def motion(self, event):
        if self._state is not dragging:
            return

        self.master.config(cursor = "fleur")
        c = self.canvas

        xy = c.canvasx(event.x), c.canvasy(event.y)
        points = c.coords(self.dnd_dragged)

        offset = self.off

        if self.align:
            new_pos = (
                xy[0] - offset[0],
                xy[1] - offset[1],
            )

            m = self.mesh_step.get()
            aligned_pos = (
                int(new_pos[0] / m) * m,
                int(new_pos[1] / m) * m
            )

            align_gain = (
                aligned_pos[0] - new_pos[0],
                aligned_pos[1] - new_pos[1]
            )
        else:
            align_gain = (0, 0)

        dxy = (
            xy[0] - (points[0] + offset[0]) + align_gain[0],
            xy[1] - (points[1] + offset[1]) + align_gain[1]
        )

        #print str(points) + " - " + str(self.off)

        tags = c.gettags(self.dnd_dragged)

        if "fixed_x" not in tags:
            for idx in xrange(0, len(points), 2):
                points[idx] = dxy[0] + points[idx]

        if "fixed_y" not in tags:
            for idx in xrange(1, len(points), 2):
                points[idx] = dxy[1] + points[idx]

        #print points

        c.coords(*([self.dnd_dragged] + points))

        self.event_generate('<<DnDMoved>>')

    def up(self, event):
        if self._state is dragging:
            self.master.config(cursor = "")
            self._state = None
            self.off = None
            self.event_generate('<<DnDUp>>')
            """ Right after event. Listeners should be able to get which id
            is not dragged now. """
            del self.dnd_dragged
