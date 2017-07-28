#!/usr/bin/python2
# based on http://code.activestate.com/lists/python-list/281562/

from copy import \
    copy

from .gui_frame import \
    GUIFrame

from six.moves.tkinter import \
    Canvas, \
    RIDGE, \
    BOTH

class CanvasDnD(GUIFrame):
    def __init__(self, master,
            id_priority_sort_function = lambda ids : ids
        ):

        GUIFrame.__init__ (self, master)
        self.canvas = Canvas (self, 
            width = 100, # default width
            height = 100, # default height
            relief = RIDGE,
            background = "white",
            borderwidth = 1
        )

        self.canvas.pack(expand = 1, fill = BOTH)

        self.dragging = False
        self.off = None
        self.canvas.bind("<ButtonPress-1>", self.down, "+")
        self.canvas.bind("<ButtonRelease-1>", self.up, "+")
        self.canvas.bind("<Motion>", self.motion, "+")

        self.id_priority_sort_function = id_priority_sort_function

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

        self.dragging = True
        self.event_generate('<<DnDDown>>')

    def motion(self, event):
        if not self.dragging:
            return

        self.master.config(cursor = "fleur")
        c = event.widget

        xy = c.canvasx(event.x), c.canvasy(event.y)
        points = event.widget.coords(self.dnd_dragged)
        anchors = copy(points[:2])
        offset = self.off
        dxy = (
            xy[0] - (anchors[0] + offset[0]),
            xy[1] - (anchors[1] + offset[1]),
        )

        #print str(points) + " - " + str(self.off)

        for idx in range(len(points)):
            if "fixed_x" in c.gettags(self.dnd_dragged) and idx % 2 == 0:
                continue
            if "fixed_y" in c.gettags(self.dnd_dragged) and idx % 2 == 1:
                continue
            #print idx, xy[idx % 2], anchors[idx % 2]
            points[idx] = dxy[idx % 2] + points[idx]
    
        #print points

        event.widget.coords(*([self.dnd_dragged] + points))

        self.event_generate('<<DnDMoved>>')

    def up(self, event):
        if self.dragging:
            self.master.config(cursor = "")
            self.dragging = False
            self.off = None
            self.event_generate('<<DnDUp>>')
            """ Right after event. Listeners should be able to get which id
            is not dragged now. """
            del self.dnd_dragged
