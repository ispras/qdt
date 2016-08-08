from widgets import \
    VarMenu, \
    CanvasDnD

import Tkinter as tk

from phy import \
    Vector, \
    Segment, \
    Polygon

import math
import random
import time

from common import \
    History, \
    ML as _, \
    sign

from qemu import \
    MOp_SetDevParentBus, \
    MOp_SetDevQOMType, \
    Node, \
    DeviceNode, \
    MachineHistoryTracker

from widgets import \
    DeviceSettingsWindow

from sets import \
    Set

class NodeBox(object):
    def __init__(self, node):
        # "physics" parameters 
        self.x = 200
        self.y = 200
        self.vx = self.vy = 0
        self.offset = [0, 0]
        self.width = 50
        self.height = 50
        self.spacing = 10
        # the node cannot be moved by engine if static
        self.static = False

        self.node = node
        self.conn = None

        self.text = None
        self.text_width = 50
        self.text_height = 50
        self.padding = 10

        self.bus_padding = 20

    def get_irq_binding(self, target):
        if target:
            s2 = self.spacing/2
            p = Polygon(
                points = [
                    Vector(self.x - s2, self.y - s2),
                    Vector(
                        self.x + self.width + s2,
                        self.y - s2
                    ),
                    Vector(
                        self.x + self.width + s2,
                        self.y + self.height + s2
                    ),
                    Vector(
                        self.x - s2,
                        self.y + self.height + s2
                    )
                ],
                deepcopy = False
            )
            b = Vector(self.x + self.width/2, self.y + self.height/2)
            s = Segment(
                begin = b,
                direction = Vector(target[0] - b.x, target[1] - b.y)
            )
            s.SetLenght(self.width + self.height + 1 + self.spacing)
            i = p.Crosses(s)[0]
            x, y = i.x, i.y
        else:
            x = self.x + self.width/2
            y = self.y + self.height/2
        return x, y

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
    def __init__(self, bl):
        self.x = 200
        self.vx = 0
        self.y = self.next_y = -100000
        self.vy = 0
        self.height = self.next_height = 200000
        self.static = False
        self.extra_length = 50

        self.buslabel = bl

class BusLabel(NodeBox):
    def __init__(self, bus):
        NodeBox.__init__(self, bus)

        self.cap_size = 0.5
        self.busline = None

class ConnectionLine(object):
    def __init__(self, dev_node, bus_node):
        self.dev_node = dev_node
        self.bus_node = bus_node

        self.update()

    def update(self):
        self.y = self.dev_node.y + self.dev_node.height / 2
        self.x = min([self.bus_node.x, self.dev_node.x + self.dev_node.width / 2])
        self.width = max([self.bus_node.x, self.dev_node.x + self.dev_node.width / 2]) - self.x

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

class NodeCircle(object):
    def __init__(self):
        self.x = 200
        self.vx = 0
        self.y = 200
        self.vy = 0
        self.offset = [0, 0]
        self.r = 10
        self.static = False
        self.spacing = 0

    def overlaps_circle(self, c):
        dx = c.x + c.r - (self.x + self.r)
        dy = c.y + c.r - (self.y + self.r)
        return math.sqrt( dx * dx + dy * dy ) \
            < c.r + c.spacing + self.r + self.spacing

    def overlaps_node(self, n):
        # it is not a precise check 
        if self.x + self.r * 2 + self.spacing < n.x - n.spacing: 
            return False
        if self.y + self.r * 2 + self.spacing < n.y - n.spacing: 
            return False
        if n.x + n.width + n.spacing < self.x - self.spacing:
            return False
        if n.y + n.height + n.spacing < self.y - self.spacing:
            return False
        return True

class IRQPathCircle(NodeCircle):
    def __init__(self):
        NodeCircle.__init__(self)
        self.spacing = 0

class IRQHubCircle(NodeCircle):
    def __init__(self, hub):
        NodeCircle.__init__(self)
        self.spacing = 5
        self.node = hub

    def get_irq_binding(self, target):
        if target:
            dx = target[0] - self.x
            dy = target[1] - self.y
            d = math.sqrt( dx * dx + dy * dy )
            l = (self.r + self.spacing) / d
            x, y = self.x + dx * l + self.r, self.y + dy * l + self.r
        else:
            x, y = self.x + self.r, self.y + self.r
        return x, y

class IRQLine(object):
    def __init__(self, src_node, dst_node):
        self.src = src_node
        self.dst = dst_node
        self.arrow = None
        self.circles = []
        self.lines = []

class MachineWidget(CanvasDnD):
    EVENT_SELECT = "<<Select>>"

    def __init__(self, parent, mach_desc):
        CanvasDnD.__init__(self, parent)

        mach_desc.link()

        self.mach = mach_desc
        self.history = History()
        self.mht = MachineHistoryTracker(self.mach, self.history)

        self.id2node = {}
        self.node2id = {}
        self.dev2node = {}
        self.node2dev = {}
        self.node2idtext = {}

        self.bind(MachineWidget.EVENT_SELECT, self.on_select)
        self.ids_shown_on_select = Set([])

        self.nodes = []
        self.buslabels = []
        self.buses = []
        self.conns = []
        self.circles = []
        self.irq_lines = []

        self.velocity_k = 0.05
        self.velicity_limit = 10

        self.bus_velocity_k = 0.05
        self.bus_gravity_k = 0.2

        # radius and space between IRQ circles
        self.irq_circle_r = 10
        self.irq_circle_s = 0
        self.irq_circle_graviry = 0.02
        self.irq_arrow_length = 10
        self.irq_arrow_width2 = 2.5
        self.irq_circle_per_line_limit = 5
        self.irq_circle_total_limit = 50
        self.shown_irq_circle = None
        self.shown_irq_node = None
        self.irq_line_color = "grey"

        self.update()

        self.bind('<<DnDMoved>>', self.dnd_moved)
        self.bind('<<DnDDown>>', self.dnd_down)
        self.bind('<<DnDUp>>', self.dnd_up)
        self.dragged = []

        self.canvas.bind("<ButtonPress-3>", self.on_b3_press)
        self.canvas.bind("<ButtonRelease-3>", self.on_b3_release)

        # override super class method
        self.canvas.bind("<Motion>", self.motion_all)

        self.dragging_all = False

        self.current_ph_iteration = None
        self.invalidated = False

        self.selection_marks = []
        self.selection_mark_color = "orange"
        self.selected = []
        self.select_point = None
        self.canvas.bind("<ButtonPress-1>", self.on_b1_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_b1_release)

        self.select_frame = None
        self.select_frame_color = "green"

        self.key_state = {}
        self.canvas.bind("<KeyPress>", self.on_key_press)
        self.canvas.bind("<KeyRelease>", self.on_key_release)
        self.canvas.focus_set()

        p = VarMenu(self.winfo_toplevel(), tearoff = 0)
        p.add_command(
            label = _("Settings"),
            command = self.on_popup_single_device_settings
        )
        self.popup_single_device = p

        self.current_popup = None

        self.mht.add_on_changed(self.on_machine_changed)

    def on_machine_changed(self, op):
        if isinstance(op, MOp_SetDevQOMType):
            dev = self.mach.id2node[op.dev_id]
            node = self.dev2node[dev]
            self.update_node_text(node)
        elif isinstance(op, MOp_SetDevParentBus):
            dev = self.mach.id2node[op.dev_id]
            node = self.dev2node[dev]
            pb = dev.parent_bus
            if node.conn:
                if pb:
                    pbn = self.dev2node[pb].busline
                    node.conn.bus_node = pbn
                else:
                    conn_id = self.node2id[node.conn]
                    del self.id2node[conn_id]
                    del self.node2id[node.conn]
                    self.conns.remove(node.conn)
                    self.canvas.delete(conn_id)
                    node.conn = None
            else:
                pbn = self.dev2node[pb].busline
                self.add_conn(node, pbn)

    def on_popup_single_device_settings(self):
        id = self.selected[0]

        x0, y0 = self.canvas.canvasx(0), self.canvas.canvasy(0)
        x, y = self.canvas.coords(id)[-2:]
        x = x - x0
        y = y - y0

        dev = self.node2dev[self.id2node[id]]
        wnd = DeviceSettingsWindow(self, dev, self.mht)
        # Makes settings window always on top.
        # Is there more pythonic interface?
        # http://effbot.org/tkinterbook/wm.htm#Tkinter.Wm.attributes-method
        wnd.attributes("-topmost", 1)

        geom = "+" + str(int(self.winfo_rootx() + x)) \
             + "+" + str(int(self.winfo_rooty() + y))

        wnd.geometry(geom)

    def on_key_press(self, event):
        self.key_state[event.keycode] = True

    def on_key_release(self, event):
        self.key_state[event.keycode] = False

    def shift_pressed(self):
        try:
            if self.key_state[50]:
                return True
        except:
            pass
        try:
            if self.key_state[62]:
                return True
        except:
            pass
        return False

    def on_b1_press(self, event):
        if self.current_popup:
            self.current_popup.unpost()
            self.current_popup = None

        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.select_point = (x, y)

        self.select_frame = self.canvas.create_rectangle(
            x, y, x + 1, y + 1,
            fill = "",
            outline = self.select_frame_color
        )
        self.select_by_frame = False

    def on_b1_release(self, event):
        if not self.select_point:
            return

        x, y = self.select_point[0], self.select_point[1] 

        if self.select_by_frame:
            bbox = self.canvas.bbox(self.select_frame)
            touched = self.canvas.find_enclosed(*bbox)
        else:
            touched = self.canvas.find_overlapping(
                x - 3, y - 3, x + 3, y + 3
            )

        self.select_point = None
        self.canvas.delete(self.select_frame)
        self.select_frame = None

        touched_ids = []
        for t in touched:
            if ("DnD" in self.canvas.gettags(t)) and (t in self.id2node.keys()):
                touched_ids.append(t)
                if not self.select_by_frame:
                    break

        shift = self.shift_pressed()

        if not touched_ids:
            if not shift:
                if self.selected:
                    self.selected = []
                    self.event_generate(MachineWidget.EVENT_SELECT)
            return

        if not touched_ids:
            return

        if shift:
            for tid in touched_ids:
                if self.select_by_frame:
                    if not tid in self.selected:
                        self.selected.append(tid)
                        self.event_generate(MachineWidget.EVENT_SELECT)
                else:
                    if tid in self.selected:
                        self.selected.remove(tid)
                        self.event_generate(MachineWidget.EVENT_SELECT)
                    else:
                        self.selected.append(tid)
                        self.event_generate(MachineWidget.EVENT_SELECT)
        elif not self.selected == touched_ids:
            self.selected = list(touched_ids)
            self.event_generate(MachineWidget.EVENT_SELECT)

        self.invalidated = True

    def on_b3_press(self, event):
        if self.current_popup:
            self.current_popup.unpost()
            self.current_popup = None

        if self.dragging or self.select_point:
            return

        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

        touched_ids = self.canvas.find_overlapping(x - 3, y - 3, x + 3, y + 3)

        for tid in touched_ids:
            if not "DnD" in self.canvas.gettags(tid):
                continue
            if not tid in self.id2node:
                continue

            shift = self.shift_pressed()
            if shift:
                if not tid in self.selected:
                    self.selected.append(tid)
                    self.event_generate(MachineWidget.EVENT_SELECT)
            else:
                if not tid in self.selected:
                    self.selected = [tid]
                    self.event_generate(MachineWidget.EVENT_SELECT)

            # touched node
            tnode = self.id2node[tid]

            if not tnode in self.node2dev:
                break

            # touched device, etc..
            tdev = self.node2dev[tnode]

            if isinstance(tdev, DeviceNode):
                if len(self.selected) == 1:
                    self.current_popup = self.popup_single_device

            if self.current_popup:
                try: 
                    self.current_popup.tk_popup(event.x_root, event.y_root)
                    self.current_popup.grab_release()
                except:
                    self.current_popup.grab_release()
                    self.current_popup = None

                return

            break

        #print("on_b3_press")
        event.widget.scan_mark(int(x), int(y)
        )
        self.dragging_all = True
        self.master.config(cursor = "fleur")

    def on_b3_release(self, event):
        #print("on_b3_release")
        for n in self.nodes + self.buslabels + self.circles:
            n.static = False
        self.dragging_all = False
        self.master.config(cursor = "")

    def motion_all(self, event):
        self.motion(event)
        #print("motion_all")

        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

        if self.select_point:
            apply(self.canvas.coords, [
                self.select_frame,
                self.select_point[0], self.select_point[1],
                x, y
            ])
            self.select_by_frame = True
            return

        if self.shown_irq_circle:
            if not self.shown_irq_circle in self.canvas.find_overlapping(
                x - 3, y - 3, x + 3, y + 3
            ):
                self.canvas.delete(self.shown_irq_circle)
                self.shown_irq_circle = None
                self.shown_irq_node = None
        else:
            for c in self.circles:
                if not isinstance(c, IRQPathCircle):
                    continue
                dx, dy = x - (c.x + c.r), y - (c.y + c.r)
                if c.r >= math.sqrt(dx * dx + dy * dy):
                    self.shown_irq_circle = self.canvas.create_oval(
                        c.x, c.y,
                        c.x + c.r * 2, c.y + c.r * 2,
                        fill = "white",
                        tags = "DnD"
                    )
                    self.shown_irq_node = c
                    break

        if not self.dragging_all:
            return

        event.widget.scan_dragto(
            int(event.widget.canvasx(event.x)),
            int(event.widget.canvasy(event.y)),
            gain = 1
        )
        event.widget.scan_mark(
            int(event.widget.canvasx(event.x)),
            int(event.widget.canvasy(event.y))
        )

        # cancel current physic iteration if moved
        self.current_ph_iteration = None
        self.invalidated = True
        self.select_point = None
        self.canvas.delete(self.select_frame)
        self.select_frame = None

    def dnd_moved(self, event):
        id = self.canvas.find_withtag(tk.CURRENT)[0]
        if id == self.shown_irq_circle:
            node = self.shown_irq_node
        else:
            node = self.id2node[id]

        points = self.canvas.coords(tk.CURRENT)[:2]
        points[0] = points[0] - node.offset[0]
        points[1] = points[1] - node.offset[1]

        # moving of non-selected item while other are selected
        if self.selected:
            if not id in self.selected:
                if self.shift_pressed():
                    self.selected.append(id)
                else:
                    self.selected = []
                self.event_generate(MachineWidget.EVENT_SELECT)

        if self.selected:
            # offset
            ox = points[0] - node.x
            oy = points[1] - node.y

            for i in self.selected:
                if i == self.shown_irq_circle:
                    continue

                n = self.id2node[i]
                n.x, n.y = n.x + ox, n.y + oy

                if isinstance(n, NodeBox):
                    self.apply_node(n)
        else:
            node.x = points[0]
            node.y = points[1]

            if isinstance(node, NodeBox):
                self.apply_node(node)

        # cancel current physic iteration if moved
        self.current_ph_iteration = None
        self.invalidated = True
        self.select_point = None
        self.canvas.delete(self.select_frame)
        self.select_frame = None

    def dnd_down(self, event):
        id = self.canvas.find_withtag(tk.CURRENT)[0]
        if id == self.shown_irq_circle:
            node = self.shown_irq_node
        else:
            node = self.id2node[id]

        if id in self.selected:
            for i in self.selected:
                if i == self.shown_irq_circle:
                    continue

                n = self.id2node[i]

                n.static = True
                self.dragged.append(n)
        else:
            node.static = True
            self.dragged.append(node)

    def dnd_up(self, event):
        for n in self.dragged:
            n.static = False
        self.dragged = []

    def update(self):
        irqs = list(self.mach.irqs)

        for hub in self.mach.irq_hubs:
            if hub in self.dev2node.keys():
                continue
            hub_node = IRQHubCircle(hub)

            self.dev2node[hub] = hub_node
            self.node2dev[hub_node] = hub

            self.add_irq_hub(hub_node)

        for bus in self.mach.buses:
            if bus in self.dev2node.keys():
                continue

            node = BusLabel(bus)

            self.dev2node[bus] = node
            self.node2dev[node] = bus

            self.add_buslabel(node)

        for dev in self.mach.devices:
            if not dev in self.dev2node.keys():
                node = NodeBox(dev)

                self.dev2node[dev] = node
                self.node2dev[node] = dev

                self.add_node(node, dev.buses)
            else:
                node = self.dev2node[dev]

            if node.conn:
                continue

            if not dev.parent_bus:
                continue

            pb = dev.parent_bus
            if not pb in self.dev2node.keys():
                continue
            pbn = self.dev2node[pb].busline

            self.add_conn(node, pbn)

        for irq in irqs:
            if irq in self.dev2node.keys():
                continue

            src = self.dev2node[irq.src[0]]
            dst = self.dev2node[irq.dst[0]]

            line = IRQLine(src, dst)

            self.dev2node[irq] = line
            self.node2dev[line] = irq

            self.add_irq_line(line)

        for hub in self.mach.irq_hubs:
            for src_desc in hub.srcs:
                if src_desc in self.dev2node.keys():
                    continue

                src = self.dev2node[src_desc[0]]
                dst = self.dev2node[hub]

                line = IRQLine(src, dst)

                self.dev2node[src_desc] = line
                self.node2dev[line] = src_desc

                self.add_irq_line(line)

            for dst_desc in hub.dsts:
                if dst_desc in self.dev2node.keys():
                    continue

                src = self.dev2node[hub]
                dst = self.dev2node[dst_desc[0]]

                line = IRQLine(src, dst)

                self.dev2node[dst_desc] = line
                self.node2dev[line] = dst_desc

                self.add_irq_line(line)


    def ph_iterate(self, t_limit_sec):
        if not self.current_ph_iteration:
            self.current_ph_iteration = self.ph_iterate_co()

            if self.invalidated:
                self.ph_sync()
                self.invalidated = False

        t0 = time.time()
        for x in self.current_ph_iteration:
            t1 = time.time()
            dt = t1 - t0
            t_limit_sec = t_limit_sec - dt
            if t_limit_sec <= 0:
                return 0
            t0 = t1

        self.current_ph_iteration = None
        self.ph_apply()

        t1 = time.time()
        dt = t1 - t0
        t_limit_sec = t_limit_sec - dt
        if t_limit_sec <= 0:
            return 0
        else:
            return t_limit_sec

    def ph_sync(self):
        for n in self.nodes:
            dev = self.node2dev[n]

            if dev.buses:
                min_x = n.x + n.width + n.bus_padding
                max_x = n.x - n.bus_padding

                for bus in dev.buses:
                    b = self.dev2node[bus]

                    x = b.x + b.offset[0] - n.bus_padding
                    if min_x > x:
                        min_x = x

                    x = b.x + b.offset[0] + n.bus_padding
                    if max_x < x:
                        max_x = x

                n.width = max([max_x - min_x, n.text_width + n.padding])
                if n.x > min_x:
                    n.x = min_x
                if n.x + n.width < max_x:
                    n.x = max_x - n.width

            self.ph_apply_node(n)

        for bl in self.buslabels:
            self.ph_apply_buslabel(bl)

        for b in self.buses:
            # update
            bus = self.node2dev[b.buslabel]

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

            y = b.buslabel.y - b.extra_length
            if min_y > y:
                min_y = y

            y = b.buslabel.y + b.buslabel.height + b.extra_length
            if max_y < y:
                max_y = y

            b.x = b.buslabel.x + b.buslabel.offset[0]
            b.y = min_y
            b.height = max_y - min_y

            self.ph_apply_bus(b)

        for c in self.conns:
            c.update()
            self.ph_apply_conn(c)

        for h in self.circles:
            if isinstance(h, IRQHubCircle):
                self.ph_apply_hub(h)
            elif self.shown_irq_node == h:
                points = [
                    h.x, h.y,
                    h.x + 2 * h.r, h.y + 2 * h.r
                ]

                apply(self.canvas.coords, [self.shown_irq_circle] + points)

        total_circles = 0
        for l in self.irq_lines:
            self.ph_process_irq_line(l)
            total_circles = total_circles + len(l.circles)

        if total_circles > self.irq_circle_total_limit:
            self.irq_circle_per_line_limit = int(self.irq_circle_total_limit /
                len(self.irq_lines))
            if self.irq_circle_per_line_limit == 0:
                self.irq_circle_per_line_limit = 1

            #print "Total circles: " + str(total_circles) + ", CPL: " + \
            #    str(self.irq_circle_per_line_limit) 

        marks = len(self.selection_marks)
        selects = len(self.selected)

        if marks < selects:
            for i in xrange(0, selects - marks):
                self.selection_marks.append(self.canvas.create_rectangle(
                    0,0,0,0,
                    outline = self.selection_mark_color,
                    fill = ""
                ))
        elif marks > selects:
            for id in self.selection_marks[selects:]:
                self.canvas.delete(id)
            self.selection_marks = self.selection_marks[:selects]

        for idx, sid in enumerate(self.selected):
            bbox = self.canvas.bbox(sid)
            apply(self.canvas.coords, [
                self.selection_marks[idx],
                bbox[0] - 1, bbox[1] - 1,
                bbox[2] + 1, bbox[3] + 1
            ])

        for n, idtext in list(self.node2idtext.iteritems()):
            dev = self.node2dev[n]
            if isinstance(dev, Node):
                if isinstance(n, NodeCircle):
                    bbox = self.canvas.bbox(idtext)
                    coords = [n.x + n.r, n.y + n.r]
                else:
                    coords = [n.x + n.width + n.spacing,
                              n.y + n.height + n.spacing]
                self.canvas.coords(idtext, *coords)

    def on_select(self, event):
        still_selected = Set([])
        for sid in self.selected:
            node = self.id2node[sid]
            still_selected.add(node)

        for n in self.ids_shown_on_select - still_selected:
            self.hide_node_id(n)
        for n in still_selected - self.ids_shown_on_select:
            self.show_node_id(n)
        self.ids_shown_on_select = still_selected

    def show_node_id(self, node):
        idtext = self.canvas.create_text(
            0, 0,
            text = str(node.node.id),
            state = tk.DISABLED
        )
        self.node2idtext[node] = idtext

    def hide_node_id(self, node):
        idtext = self.node2idtext[node]
        self.canvas.delete(idtext)
        del self.node2idtext[node]

    def ph_apply(self):
        for n in self.nodes:
            if n.static:
                continue

            self.ph_move(n)

        for bl in self.buslabels:
            if n.static:
                continue

            self.ph_move(bl)

        for h in self.circles:
            if h.static:
                continue

            self.ph_move(h)

        self.ph_sync()

    def ph_iterate_co(self):
        for n in self.nodes + self.buslabels + self.circles:
            n.vx = n.vy = 0

        yield

        nbl = self.nodes + self.buslabels

        for idx, n in enumerate(nbl):
            for n1 in nbl[idx + 1:]:
                if not n.overlaps(n1):
                    continue

                w2 = n.width / 2
                h2 = n.height / 2

                w12 = n1.width / 2
                h12 = n1.height / 2

                # distance vector from n center to n1 center
                dx = n1.x + w12 - (n.x + w2)

                while dx == 0:
                    dx = sign(random.random() - 0.5)

                dy = n1.y + h12 - (n.y + h2) 

                while dy == 0:
                    dy = sign(random.random() - 0.5)

                w = n.width + 2 * n.spacing
                w1 = n1.width + 2 * n1.spacing

                h = n.height + 2 * n.spacing
                h1 = n1.height + 2 * n1.spacing

                xscale = float(w) / (w + w1)
                yscale = float(h) / (h + h1)

                # intrusion point, inside box physical border (including
                # spacing)
                # The intrusion point is shifted from interval's middle point
                # to the smallest box center.
                ix = dx * xscale
                iy = dy * yscale

                # collision point, at box physical border
                if abs(iy) > abs(ix):
                    cy = (h2 + n.spacing) * sign(iy)
                    cx = ix * cy / iy
                else:
                    cx = (w2 + n.spacing) * sign(ix)
                    cy = iy * cx / ix

                # reaction vector, the direction is from intrusion point to
                # collision point
                rx = ix - cx
                ry = iy - cy

                n.vx = n.vx + rx * self.velocity_k
                n.vy = n.vy + ry * self.velocity_k
                n1.vx = n1.vx - rx * self.velocity_k
                n1.vy = n1.vy - ry * self.velocity_k

                # Artificial sleep for time management test 
                #time.sleep(0.001)

            yield

            for b in self.buses:
                if not n.touches(b):
                    continue

                if n == b.buslabel:
                    continue

                parent_device = self.node2dev[b.buslabel].parent_device
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

            yield

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

            yield

            for hub in self.circles:
                if not hub.overlaps_node(n):
                    continue

                w2 = n.width / 2
                h2 = n.height / 2

                # distance vector from n center to n1 center
                dx = hub.x + hub.r - (n.x + w2)

                while dx == 0:
                    dx = sign(random.random() - 0.5)

                dy = hub.y + hub.r - (n.y + h2) 

                while dy == 0:
                    dy = sign(random.random() - 0.5)

                w = n.width + 2 * n.spacing
                h = n.height + 2 * n.spacing
                d = (hub.r + hub.spacing) * 2


                xscale = float(w) / (w + d)
                yscale = float(h) / (h + d)

                ix = dx * xscale
                iy = dy * yscale

                # collision point, at box physical border
                if abs(iy) > abs(ix):
                    cy = (h2 + n.spacing) * sign(iy)
                    cx = ix * cy / iy
                else:
                    cx = (w2 + n.spacing) * sign(ix)
                    cy = iy * cx / ix

                rx = ix - cx
                ry = iy - cy

                if isinstance(hub, IRQHubCircle):
                    n.vx = n.vx + rx * self.velocity_k
                    n.vy = n.vy + ry * self.velocity_k

                hub.vx = hub.vx - rx * self.velocity_k
                hub.vy = hub.vy - ry * self.velocity_k

            yield

        for idx, h in enumerate(self.circles):
            for h1 in self.circles[idx + 1:]:
                #if bool(isinstance(h1, IRQPathCircle)) != bool(isinstance(h, IRQPathCircle)):
                #    continue

                if not h.overlaps_circle(h1):
                    continue

                dx = h1.x + h1.r - (h.x + h.r)

                while dx == 0:
                    dx = sign(random.random() - 0.5)

                dy = h1.y + h1.r - (h.y + h.r)

                while dy == 0:
                    dy = sign(random.random() - 0.5)

                scale = float(h.r) / (h.r + h1.r)

                ix = dx * scale
                iy = dy * scale

                ir = math.sqrt(ix * ix + iy * iy)
                k = (h.r + h.spacing) / ir

                cx = ix * k
                cy = iy * k

                rx = ix - cx
                ry = iy - cy

                if not (isinstance(h, IRQHubCircle) and isinstance(h1, IRQPathCircle)):
                    h.vx = h.vx + rx * self.velocity_k
                    h.vy = h.vy + ry * self.velocity_k
                if not (isinstance(h1, IRQHubCircle) and isinstance(h, IRQPathCircle)):
                    h1.vx = h1.vx - rx * self.velocity_k
                    h1.vy = h1.vy - ry * self.velocity_k

            yield

        for l in self.irq_lines:
            if len(l.circles) < 2:
                continue

            c = l.circles[0]
            x, y = l.src.get_irq_binding((c.x, c.y))
            dx = x - (c.x + c.r)
            dy = y - (c.y + c.r)
            c.vx = c.vx + dx * self.irq_circle_graviry
            c.vy = c.vy + dy * self.irq_circle_graviry

            c = l.circles[-1]
            x, y = l.dst.get_irq_binding((c.x, c.y))
            dx = x - (c.x + c.r)
            dy = y - (c.y + c.r)
            c.vx = c.vx + dx * self.irq_circle_graviry
            c.vy = c.vy + dy * self.irq_circle_graviry

            for idx, c in enumerate(l.circles[:-1]):
                c1 = l.circles[idx + 1]

                dx = c1.x + c1.r - (c.x + c.r)
                dy = c1.y + c1.r - (c.y + c.r)

                c.vx = c.vx + dx * self.irq_circle_graviry
                c.vy = c.vy + dy * self.irq_circle_graviry
                c1.vx = c1.vx - dx * self.irq_circle_graviry
                c1.vy = c1.vy - dy * self.irq_circle_graviry

            yield

        raise StopIteration()

    def ph_apply_conn(self, c):
        id = self.node2id[c]
        points = [
            c.x, c.y,
            c.x + c.width, c.y
        ]

        apply(self.canvas.coords, [id] + points)

    def ph_apply_buslabel(self, bl):
        id = self.node2id[bl]
        points = [bl.x + bl.width / 2, bl.y,
            bl.x + bl.width, bl.y + bl.cap_size * (bl.text_height + bl.padding),
            bl.x + bl.width, bl.y + (1 + bl.cap_size) * (bl.text_height + bl.padding),
            bl.x + bl.width / 2, bl.y + bl.height,
            bl.x, bl.y + (1 + bl.cap_size) * (bl.text_height + bl.padding),
            bl.x, bl.y + bl.cap_size * (bl.text_height + bl.padding)]

        apply(self.canvas.coords, [id] + points)
        self.apply_node(bl)

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

    def ph_apply_hub(self, h):
        id = self.node2id[h]
        points = [
            h.x, h.y,
            h.x + 2 * h.r, h.y + 2 * h.r
        ]

        apply(self.canvas.coords, [id] + points)

    def ph_process_irq_line(self, l):
        changed = False

        for i, seg in enumerate(l.lines):
            if i == 0:
                if l.circles:
                    c = l.circles[0]
                    x1, y1 = c.x + c.r, c.y + c.r
                    x0, y0 = l.src.get_irq_binding((x1, y1))
                else:
                    x1, y1 = l.dst.get_irq_binding(None)
                    x0, y0 = l.src.get_irq_binding((x1, y1))
                    x1, y1 = l.dst.get_irq_binding((x0, y0))
            elif i == len(l.lines) - 1:
                if l.circles:
                    c = l.circles[i - 1]
                    x0, y0 = c.x + c.r, c.y + c.r
                    x1, y1 = l.dst.get_irq_binding((x0, y0))
                else:
                    x0, y0 = l.src.get_irq_binding(None)
                    x1, y1 = l.dst.get_irq_binding((x0, y0))
                    x0, y0 = l.src.get_irq_binding((x1, y1))
            else:
                c = l.circles[i - 1]
                x0, y0 = c.x + c.r, c.y + c.r
                c = l.circles[i]
                x1, y1 = c.x + c.r, c.y + c.r

            # Do not change lines during dragging it could delete currently
            # dragged circle
            line_circles = len(l.circles)

            if not (   self.dragging 
                    or changed 
                    or self.irq_circle_per_line_limit < line_circles
                ):
                dx = x1 - x0
                dy = y1 - y0
                d = math.sqrt( dx * dx + dy * dy )

                d1 = (self.irq_circle_r + self.irq_circle_s) * 2

                if d > 2 * d1:
                    x2 = (x0 + x1) / 2
                    y2 = (y0 + y1) / 2

                    c = IRQPathCircle()
                    c.x, c.y = x2 - self.irq_circle_r, y2 - self.irq_circle_r
                    c.r = self.irq_circle_r

                    self.circles.append(c)

                    id = self.canvas.create_line(
                        0, 0, 1, 1,
                        fill = self.irq_line_color
                    )
                    self.canvas.lower(id)

                    l.circles.insert(i, c)
                    l.lines.insert(i + 1, id)

                    x1 = x2
                    y1 = y2

                    changed = True
                elif (    d < 1.5 * d1
                       or line_circles > self.irq_circle_per_line_limit
                    ):
                    if i < len(l.lines) - 1:
                        # not last line

                        self.canvas.delete(l.lines.pop(i + 1))
                        c = l.circles.pop(i)

                        if c == self.shown_irq_node:
                            self.canvas.delete(self.shown_irq_circle)
                            self.shown_irq_node = None
                            self.shown_irq_circle = None

                        self.circles.remove(c)

                        if i < len(l.circles):
                            c = l.circles[i]
                            x1, y1 = c.x + c.r, c.y + c.r
                        else:
                            x1, y1 = l.dst.get_irq_binding((x0, y0))

                        changed = True

            apply(self.canvas.coords, [seg] + [x0, y0, x1, y1])

        # update arrow
        # direction
        dx, dy = x1 - x0, y1 - y0
        # normalize direction
        dl = math.sqrt(dx * dx + dy * dy)

        if dl == 0:
            # next time last segment length should be non-zero
            return

        dx, dy = dx / dl, dy / dl
        # normal vector, 90 degrees
        nx, ny = dy, -dx
        # offsets
        ox, oy = nx * self.irq_arrow_width2, ny * self.irq_arrow_width2
        dx, dy = dx * self.irq_arrow_length, dy * self.irq_arrow_length

        arrow_coords = [
            l.arrow,
            x1, y1,
            x1 - dx + ox, y1 - dy + oy,
            x1 - dx - ox, y1 - dy - oy, 
        ]
        apply(self.canvas.coords, arrow_coords)

    def ph_run(self):
        rest = self.ph_iterate(0.01)
        if rest < 0.001:
            rest = 0.001

        self.after(int(rest * 1000), self.ph_run)

    def update_node_text(self, node):
        text = node.node.qom_type
        if text.startswith("TYPE_"):
            text = text[5:]
        self.canvas.itemconfig(node.text, text = text)

        t_bbox = self.canvas.bbox(node.text)
        node.text_width = t_bbox[2] - t_bbox[0]
        node.text_height = t_bbox[3] - t_bbox[1]

        node.width = node.text_width + node.padding
        node.height = node.text_height + node.padding

    def add_node(self, node, fixed_x):
        node.text = self.canvas.create_text(
            node.x, node.y,
            state = tk.DISABLED
        )

        self.update_node_text(node)

        # todo: replace rectangle with image
        if fixed_x:
            tags = ("DnD", "fixed_x")
        else:
            tags = "DnD"

        id = self.canvas.create_rectangle(
            node.x, node.y,
            node.x + node.width,
            node.y + node.height,
            fill = "white",
            tag = tags
        )

        self.id2node[id] = node
        self.node2id[node] = id

        self.canvas.lift(node.text)

        self.nodes.append(node)

    def add_irq_hub(self, hub):
        id = self.canvas.create_oval(
            0, 0, 1, 1,
            fill = "white",
            tag = "DnD"
        )

        self.id2node[id] = hub
        self.node2id[hub] = id

        self.circles.append(hub)
        self.ph_apply_hub(hub)

    def add_irq_line(self, line):
        id = self.canvas.create_line(
            0, 0, 1, 1,
            fill = self.irq_line_color
        )

        self.canvas.lower(id)
        line.lines.append(id)

        id = self.canvas.create_polygon(
            0, 0, 0, 0, 0, 0,
            fill = self.irq_line_color
        )
        line.arrow = id
        self.canvas.lower(id)

        self.irq_lines.append(line)

    def add_bus(self, bus):
        id = self.canvas.create_line(
            0, 0, 0, 0
        )
        self.canvas.lower(id)

        self.id2node[id] = bus
        self.node2id[bus] = id

        self.buses.append(bus)

    def add_buslabel(self, bl):
        node = BusLine(bl)
        self.add_bus(node)
        bl.busline = node

        id = self.canvas.create_text(
            bl.x, bl.y,
            text = bl.node.gen_child_name_for_bus(),
            state = tk.DISABLED
        )
        bl.text = id

        t_bbox = self.canvas.bbox(id)
        bl.text_width = t_bbox[2] - t_bbox[0]
        bl.text_height = t_bbox[3] - t_bbox[1]

        bl.width = bl.text_width + bl.padding
        bl.height = (1 + 2 * bl.cap_size) * (bl.text_height + bl.padding)
        bl.offset = [bl.width / 2, 0]

        id = self.canvas.create_polygon(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            fill = "white",
            outline = "black",
            tag = "DnD"
        )

        self.id2node[id] = bl
        self.node2id[bl] = id

        self.canvas.lift(id)
        self.canvas.lift(bl.text)

        self.buslabels.append(bl)

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

    def GetLayout(self):
        layout = {}

        for n in self.nodes:
            layout[n.node.id] = (n.x, n.y)

        for h in self.circles:
            if isinstance(h, IRQHubCircle):
                layout[self.node2dev[h].id] = (h.x, h.y)

        for bl in self.buslabels:
            layout[bl.node.id] = (bl.x, bl.y)

        return layout

    def SetLayout(self, l):
        layout_bak = self.GetLayout()
        try:
            for id, desc in l.iteritems():
                if id == -1:
                    continue
                dev = self.mach.id2node[id]
                if not dev:
                    continue
                n = self.dev2node[dev]
                n.x, n.y = desc[0], desc[1]
        except:
            # if new layout is incorrect then restore previous one
            self.SetLayout(layout_bak)
