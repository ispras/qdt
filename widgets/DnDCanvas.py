#!/usr/bin/python2
# based on http://code.activestate.com/lists/python-list/281562/

import copy
import Tkinter
tk = Tkinter

class CanvasDnD(tk.Frame):
    def __init__(self, master):
        self.master = master

        tk.Frame.__init__ (self, master)
        self.canvas = tk.Canvas (self, 
            width = 100, # default width
            height = 100, # default height
            relief = tk.RIDGE,
            background = "white",
            borderwidth = 1
        )

        self.canvas.pack(expand = 1, fill = tk.BOTH)

        self.dragging = False
        self.off = None
        self.canvas.tag_bind("DnD", "<ButtonPress-1>", self.down)
        self.canvas.tag_bind("DnD", "<ButtonRelease-1>", self.up)
        self.canvas.bind("<Motion>", self.motion)

    def down(self, event):
        xy = event.widget.canvasx(event.x), event.widget.canvasy(event.y)
        offset = event.widget.coords(tk.CURRENT)
        self.off = [xy[0] - offset[0], xy[1] - offset[1]]

        #print str(xy) + " - " + str(self.off)

        self.dnd_dragged = self.canvas.find_withtag(tk.CURRENT)[0]

        self.dragging = True
        self.event_generate('<<DnDDown>>')

    def motion(self, event):
        if not self.dragging:
            return

        self.master.config(cursor = "fleur")
        cnv = event.widget

        xy = cnv.canvasx(event.x), cnv.canvasy(event.y)
        points = event.widget.coords(tk.CURRENT)
        anchors = copy.copy(points[:2])

        #print str(points) + " - " + str(self.off)

        for idx in range(len(points)):
            if "fixed_x" in cnv.gettags(tk.CURRENT) and idx % 2 == 0:
                continue
            if "fixed_y" in cnv.gettags(tk.CURRENT) and idx % 2 == 1:
                continue
            #print idx, xy[idx % 2], anchors[idx % 2]
            mouse = xy[idx % 2]
            zone = anchors[idx % 2]
            offset = self.off[idx % 2]
            points[idx] = mouse - offset - zone + points[idx]
    
        #print points

        apply(event.widget.coords, [tk.CURRENT] + points)

        self.event_generate('<<DnDMoved>>')

    def up(self, event):
        self.master.config(cursor = "")
        self.dragging = False
        self.off = None
        self.event_generate('<<DnDUp>>')
        """ Right after event. Listeners should be able to get which id
        is not dragged now. """
        del self.dnd_dragged
