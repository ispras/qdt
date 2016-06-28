#!/usr/bin/python2

from examples import \
    Q35MachineNode_2_6_0

from widgets import \
    CanvasDnD

import Tkinter as tk

import math
import random
import copy

def sign(x): return 1 if x >= 0 else -1

class NodeBox(object):
    def __init__(self, node):
        # "physics" parameters 
        self.x = 200
        self.y = 200
        self.vx = self.vy = 0
        self.width = 50
        self.height = 50
        self.spacing = 10
        # the node cannot be moved by engine if static
        self.static = False

        self.node = node
        self.conn = None

        self.text = None
        self.padding = 10

    def overlaps(self, n):
        if n.x - n.spacing > self.x + self.width + self.spacing:
            return False
        if n.x + n.width + n.spacing < self.x - self.spacing:
            return False
        if n.y - n.spacing > self.y + self.height + self.spacing:
            return False
        if n.y + n.height + n.spacing < self.y - self.spacing:
            return False
        return True

    def touches_conn(self, c):
        if self.y - self.spacing > c.y:
            return False
        if self.y + self.height + self.spacing < c.y:
            return False
        if self.x + self.width + self.spacing < c.x:
            return False
        if self.x - self.spacing > c.x + c.width:
            return False
        return True

    def touches(self, l):
        if self.x - self.spacing > l.x:
            return False
        if self.x + self.width + self.spacing < l.x:
            return False
        if self.y - self.spacing > l.y + l.height:
            return False
        if self.y + self.height + self.spacing < l.y:
            return False
        return True

class BusLine(object):
    def __init__(self, bus):
        self.x = 200
        self.vx = 0
        self.y = -100000
        self.vy = 0
        self.height = 200000
        self.static = False
        self.extra_length = 50

        self.bus = bus

class ConnectionLine(object):
    def __init__(self, dev_node, bus_node):
        self.dev_node = dev_node
        self.bus_node = bus_node

        self.update()

    def update(self):
        self.y = self.dev_node.y + self.dev_node.height/2
        self.x = min([self.bus_node.x, self.dev_node.x])
        self.width = max([self.bus_node.x, self.dev_node.x]) - self.x

    def crosses(self, b):
        if self.x > b.x:
            return False
        if self.y < b.y:
            return False
        if self.x + self.width < b.x:
            return False
        if b.y + b.height < self.y:
            return False
        return True

class MachineWidget(CanvasDnD):
    def __init__(self, parent, mach_desc):
        CanvasDnD.__init__(self, parent)

        mach_desc.link()

        self.mach = mach_desc

        self.id2node = {}
        self.node2id = {}
        self.dev2node = {}
        self.node2dev = {}

        self.nodes = []
        self.buses = []
        self.conns = []

        self.velocity_k = 0.05
        self.velicity_limit = 10

        self.bus_velocity_k = 0.05
        self.bus_gravity_k = 0.2

        self.update()

        self.bind('<<DnDMoved>>', self.dnd_moved)
        self.bind('<<DnDDown>>', self.dnd_down)
        self.bind('<<DnDUp>>', self.dnd_up)
        self.dragged = []

        self.canvas.bind("<ButtonPress-1>", self.down_all)
        self.canvas.bind("<ButtonRelease-1>", self.up_all)

    def down_all(self, event):
        if self.dragging:
            return
        #print("down_all")
        event.widget.bind("<Motion>", self.motion_all)
        event.widget.scan_mark(
            int(event.widget.canvasx(event.x)),
            int(event.widget.canvasy(event.y))
        )

    def up_all(self, event):
        #print("up_all")
        event.widget.unbind("<Motion>")
        for n in self.nodes + self.buses:
            n.static = False

    def motion_all(self, event):
        #print("motion_all")
        event.widget.scan_dragto(
            int(event.widget.canvasx(event.x)),
            int(event.widget.canvasy(event.y)),
            gain = 1
        )

        for id, node in self.id2node.iteritems():
            if isinstance(node, ConnectionLine):
                continue

            points = self.canvas.coords(id)[:2]
            node.x = points[0]
            node.y = points[1]
            node.static = True

    def dnd_moved(self, event):
        id = self.canvas.find_withtag(tk.CURRENT)[0]
        node = self.id2node[id]

        points = self.canvas.coords(tk.CURRENT)[:2]
        node.x = points[0]
        node.y = points[1]

        self.apply_node(node)

    def dnd_down(self, event):
        id = self.canvas.find_withtag(tk.CURRENT)[0]
        node = self.id2node[id]

        node.static = True
        self.dragged.append(node)

    def dnd_up(self, event):
        for n in self.dragged:
            n.static = False
        self.dragged = []

    def update(self):
        for bus in self.mach.buses:
            if bus in self.dev2node.keys():
                continue

            node = BusLine(bus)

            self.dev2node[bus] = node
            self.node2dev[node] = bus

            self.add_bus(node)

        for dev in self.mach.devices:
            if not dev in self.dev2node.keys():
                node = NodeBox(dev)
    
                self.dev2node[dev] = node
                self.node2dev[node] = dev
    
                self.add_node(node)
            else:
                node = self.dev2node[dev]

            if node.conn:
                continue

            if not dev.parent_bus:
                continue

            pb = dev.parent_bus
            if not pb in self.dev2node.keys():
                continue
            pbn = self.dev2node[pb]

            self.add_conn(node, pbn)

    def ph_iterate(self):
        for n in self.nodes + self.buses:
            n.vx = n.vy = 0

        for n in self.nodes:
            for n1 in self.nodes:
                if n1 == n:
                    continue
                if not n.overlaps(n1):
                    continue

                w2 = (n.width + n1.width) / 2
                h2 = (n.height + n1.height) / 2

                dx = n1.x - n.x

                while dx == 0:
                    dx = sign(random.random() - 0.5)

                dy = n1.y - n.y

                while dy == 0:
                    dy = sign(random.random() - 0.5)

                ix = dx - sign(dx) * (w2 + n.spacing + n1.spacing)

                # When nodes touches each other vertically (dx is near to 0,
                # dy is near to h2) the x-intersection (xi) is very big.
                # Which is actually wrong. Fix it up using abs(dx / dy)
                # coefficient. Note that the evaluation is symmetric for
                # horizontal touch the.
                n.vx = n.vx + ix * self.velocity_k * abs(dx / dy)

                iy = dy - sign(dy) * (h2 + n.spacing + n1.spacing)

                n.vy = n.vy + iy * self.velocity_k * abs(dy / dx)

            for b in self.buses:
                if not n.touches(b):
                    continue

                parent_device = self.node2dev[b].parent_device
                if parent_device:
                    parent_node = self.dev2node[parent_device]
                    if parent_node == n:
                        continue

                w2 = n.width / 2
                dx = b.x - (n.x + w2)

                while dx == 0:
                    dx = sign(random.random() - 0.5)

                ix = dx - sign(dx) * (w2 + n.spacing)

                n.vx = n.vx + ix * self.bus_velocity_k

                if parent_device and parent_node:
                    parent_node.vx = parent_node.vx - ix * self.velocity_k

            for c in self.conns:
                if n.conn == c:
                    continue

                if not n.touches_conn(c):
                    continue

                h2 = n.height / 2
                dy = c.y - (n.y + h2)

                while dy == 0:
                    dy = sign(random.random() - 0.5)

                iy = dy - sign(dy) * (h2 + n.spacing)

                n.vy = n.vy + iy * self.bus_velocity_k
                c.dev_node.vy = c.dev_node.vy - iy * self.bus_velocity_k

        for b in self.buses:
            bus = self.node2dev[b]

            parent_device = bus.parent_device

            if parent_device:
                parent_node = self.dev2node[parent_device]
                min_y = parent_node.y - b.extra_length
                max_y = parent_node.y + parent_node.height + b.extra_length
            else:
                min_y = b.y + b.height + b.extra_length
                max_y = b.y - b.extra_length

            for dev in bus.devices:
                n = self.dev2node[dev]

                y = n.y - b.extra_length
                if min_y > y:
                    min_y = y

                y = n.y + n.height + b.extra_length
                if max_y < y:
                    max_y = y

            b.y = min_y
            b.height = max_y - min_y

            if not parent_device:
                continue

            dx = parent_node.x + parent_node.width / 2 - b.x
            if dx == 0:
                continue

            b.vx = b.vx + dx * self.bus_gravity_k

        for n in self.nodes:
            if n.static:
                continue

            self.ph_move(n)
            self.ph_apply_node(n)

        for b in self.buses:
            self.ph_move(b)
            self.ph_apply_bus(b)

        for c in self.conns:
            c.update()
            self.ph_apply_conn(c)

    def ph_apply_conn(self, c):
        id = self.node2id[c]
        points = [
            c.x, c.y,
            c.x + c.width, c.y
        ]

        apply(self.canvas.coords, [id] + points)

    def ph_apply_bus(self, b):
        id = self.node2id[b]
        points = [
            b.x, b.y,
            b.x, b.y + b.height
        ]

        apply(self.canvas.coords, [id] + points)

    def ph_move(self, n):
        if abs(n.vx) > self.velicity_limit:
            n.vx = sign(n.vx) * self.velicity_limit
        if abs(n.vy) > self.velicity_limit:
            n.vy = sign(n.vy) * self.velicity_limit

        n.x = n.x + n.vx
        n.y = n.y + n.vy

    def apply_node(self, n):
        p = [n.x + n.width / 2, n.y + n.height / 2]
        apply(self.canvas.coords, [n.text] + p)

    def ph_apply_node(self, n):
        id = self.node2id[n]
        points = [
            n.x, n.y,
            n.x + n.width, n.y + n.height
        ]

        apply(self.canvas.coords, [id] + points)
        self.apply_node(n)

    def ph_run(self):
        self.ph_iterate()
        self.after(10, self.ph_run)

    def add_node(self, node):
        text = node.node.qom_type
        if text.startswith("TYPE_"):
            text = text[5:]

        id = self.canvas.create_text(
            node.x, node.y,
            text = text,
            state = tk.DISABLED
        )
        node.text = id

        t_bbox = self.canvas.bbox(id)
        t_width = t_bbox[2] - t_bbox[0]
        t_height = t_bbox[3] - t_bbox[1]

        node.width = t_width + node.padding
        node.height = t_height + node.padding

        # todo: replace rectangle with image
        id = self.canvas.create_rectangle(
            node.x, node.y,
            node.x + node.width,
            node.y + node.height,
            fill = "white",
            tag = "DnD"
        )
        self.id2node[id] = node
        self.node2id[node] = id

        self.canvas.lift(node.text)

        self.nodes.append(node)

    def add_bus(self, bus):
        id = self.canvas.create_line(
            bus.x, bus.y,
            bus.x, bus.y + bus.height,
        )
        self.canvas.lower(id)

        self.id2node[id] = bus
        self.node2id[bus] = id

        self.buses.append(bus)

    def add_conn(self, dev, bus):
        conn = ConnectionLine(dev, bus)

        id = self.canvas.create_line(
            conn.x, conn.y,
            conn.x + conn.width, conn.y
        )
        self.canvas.lower(id)

        self.id2node[id] = conn
        self.node2id[conn] = id

        dev.conn = conn

        self.conns.append(conn)

def main():
    root = tk.Tk()
    root.title("Drag-N-Drop Demo")

    root.grid()
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)
    root.geometry("500x500")

    cnv = MachineWidget(root, Q35MachineNode_2_6_0())
    cnv.grid(column = 0, row = 0, sticky = "NEWS")

    cnv.ph_run()

    root.mainloop()

if __name__ == '__main__':
    main()