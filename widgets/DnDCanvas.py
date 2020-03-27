#!/usr/bin/python2
# based on http://code.activestate.com/lists/python-list/281562/

__all__ = [
    "CanvasDnD"
  , "dragging"
  , "begin_drag_all"
  , "dragging_all"
  , "DRAG_GAP"
]

from .tk_unbind import (
    unbind
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


DRAG_GAP = 5


# CanvasDnD states, use them with `is` operator only
dragging = object()
begin_drag_all = object()
dragging_all = object()


class CanvasDnD(Canvas):
    unbind = unbind

    def __init__(self, master,
            id_priority_sort_function = lambda ids : ids,
            mesh_step = 20,
            **kw
        ):
        # override some defaults
        for arg, val in [
            ("width", 100),
            ("height", 100),
            ("relief", RIDGE),
            ("background", "white"),
            ("borderwidth", 1)
        ]:
            kw.setdefault(arg, val)

        Canvas.__init__ (self, master, **kw)

        self.align = False
        self.mesh_step = IntVar(value = mesh_step)
        self._state = None
        self.off = None
        self.bind("<ButtonPress-1>", self.down, "+")
        self.bind("<ButtonRelease-1>", self.up, "+")
        self.bind("<ButtonPress-3>", self.b3down, "+")
        self.bind("<ButtonRelease-3>", self.b3up, "+")
        self.bind("<Motion>", self.motion, "+")

        self.id_priority_sort_function = id_priority_sort_function

    # backward compatibility properties
    @property
    def dragging(self):
        return self._state is dragging

    def down(self, event):
        x, y = event.widget.canvasx(event.x), event.widget.canvasy(event.y)

        touched = self.find_overlapping(x - 1, y - 1, x + 1, y + 1)
        touched = [ t for t in touched if ("DnD" in self.gettags(t)) ]

        if not touched:
            return

        touched = self.id_priority_sort_function(touched)
        self.dnd_dragged = touched[0]

        offset = event.widget.coords(self.dnd_dragged)
        self.off = (x - offset[0], y - offset[1])

        #print str((x,y)) + " - " + str(self.off)

        self._state = dragging
        self.event_generate('<<DnDDown>>')

        # Emitting of item specific event allow effective monitoring for
        # very big amount of items independently. Note that each DnDDown
        # handler must check `dnd_dragged` attribute.
        self.event_generate('<<DnDDown%s>>' % self.dnd_dragged)

    def motion(self, event):
        x, y = event.x, event.y

        if self._state is begin_drag_all:
            # if user moved mouse far enough then begin dragging of all
            ox, oy = self.off
            # Use Manchester metric to speed up the check
            dx, dy = abs(x - ox), abs(y - oy)
            if dx + dy > DRAG_GAP:
                self._state = dragging_all
                self.scan_mark(ox, oy)
                self.master.config(cursor = "fleur")
                # Dragging of all items is just actually started
                self.event_generate("<<DnDAll>>")

        if self._state is dragging_all:
            self.scan_dragto(x, y, gain = 1)
            self.scan_mark(x, y)
            self.event_generate("<<DnDAllMoved>>")
            return
        elif self._state is not dragging:
            return

        self.master.config(cursor = "fleur")

        xy = self.canvasx(event.x), self.canvasy(event.y)
        points = self.coords(self.dnd_dragged)

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

        tags = self.gettags(self.dnd_dragged)

        if "fixed_x" not in tags:
            for idx in xrange(0, len(points), 2):
                points[idx] = dxy[0] + points[idx]

        if "fixed_y" not in tags:
            for idx in xrange(1, len(points), 2):
                points[idx] = dxy[1] + points[idx]

        #print points

        self.coords(*([self.dnd_dragged] + points))

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

    def b3down(self, event):
        if self._state is not None:
            return # User already using mouse for something

        # prepare for dragging of all
        self.off = event.x, event.y
        self._state = begin_drag_all

        # Dragging all items sequence begun
        self.event_generate("<<DnDAllDown>>")

    def b3up(self, _):
        if self._state in (dragging_all, begin_drag_all):
            # reset dragging of all
            self.master.config(cursor = "")
            # Dragging all items sequence finished
            self.event_generate("<<DnDAllUp>>")
            # Reset _state after the event. So, user may distinguish was a
            # dragging took place.
            self._state = None
