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
import sys

from common import \
    ML as _, \
    sign

from qemu import \
    MOp_SetChildBus, \
    BusNode, \
    IRQLine as QIRQLine, \
    MachineNodeSetLinkAttributeOperation, \
    MOp_AddIRQLine, \
    MOp_DelIRQLine, \
    MachineNodeOperation, \
    MOp_AddIRQHub, \
    MOp_SetDevParentBus, \
    MOp_SetDevQOMType, \
    Node, \
    DeviceNode, \
    IRQHub

from widgets import \
    DeviceSettingsWindow

from irq_settings import \
    IRQSettingsWindow

from bus_settings import \
    BusSettingsWindow

from sets import \
    Set

class PhObject(object):
    def __init__(self,
            # "physics" parameters
            x = 200, y = 200,
            vx = 0, vy = 0,
            w = 50, h = 50, spacing = 10,
            # the node cannot be moved by engine if static
            static = False
        ):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.spacing = spacing
        self.static = static

class PhBox(PhObject):
    def __init__(self, w = 50, h = 50, **kw):
        PhObject.__init__(self, **kw)
        self.width, self.height = w, h

class PhCircle(PhObject):
    def __init__(self, r = 10, **kw):
        PhObject.__init__(self, **kw)
        self.r = r

class MachineWidgetNodeOperation(MachineNodeOperation):
    def __init__(self, widget, *args, **kw):
        MachineNodeOperation.__init__(self, *args, **kw)

        self.w = widget

    def get_widget_entry(self):
        return (self.gen_entry(), "widget")

    def get_widget_descriptor(self):
        mach_node = self.w.mach.id2node[self.node_id]
        widget_node = self.w.dev2node[mach_node]
        return widget_node

    def __read_set__(self):
        return MachineNodeOperation.__read_set__(self) + [ self.gen_entry() ]

class MWOp_MoveNode(MachineWidgetNodeOperation):
    def __init__(self, target_x, target_y, *args, **kw):
        MachineWidgetNodeOperation.__init__(self, *args, **kw)

        self.tgt = target_x, target_y

    def __backup__(self):
        w = self.get_widget_descriptor()

        self.orig = w.x, w.y

    def __do__(self):
        w = self.get_widget_descriptor()

        w.x, w.y = self.tgt

    def __undo__(self):
        w = self.get_widget_descriptor()

        w.x, w.y = self.orig

    def __write_set__(self):
        return MachineWidgetNodeOperation.__write_set__(self) + [
            self.get_widget_entry()
        ]

class NodeBox(PhBox):
    def __init__(self, node):
        PhBox.__init__(self)

        self.offset = [0, 0]

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

class BusLine(PhBox):
    def __init__(self, bl):
        PhBox.__init__(self,
            y = -100000,
            h = 200000,
        )
        self.extra_length = 50

        self.buslabel = bl

class BusLabel(NodeBox):
    def __init__(self, bus):
        NodeBox.__init__(self, bus)

        self.cap_size = 0.5
        self.busline = None

class ConnectionLine(PhBox):
    def __init__(self, dev_node, bus_node):
        PhBox.__init__(self)
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

class NodeCircle(PhCircle):
    def __init__(self):
        PhCircle.__init__(self,
            spacing = 0
        )
        self.offset = [0, 0]

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
    def __init__(self, irq, src_node, dst_node):
        self.node = irq
        self.src = src_node
        self.dst = dst_node
        self.arrow = None
        self.circles = []
        self.lines = []

class MachineDiagramWidget(CanvasDnD):
    EVENT_SELECT = "<<Select>>"

    def __init__(self, parent, mach_desc):
        CanvasDnD.__init__(self, parent)

        mach_desc.link()

        self.mach = mach_desc
        self.mht = self.mach.project.pht.get_machine_proxy(self.mach)

        self.id2node = {}
        self.node2id = {}
        self.dev2node = {}
        self.node2dev = {}
        self.node2idtext = {}

        self.bind(MachineDiagramWidget.EVENT_SELECT, self.on_select)
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
        self.irq_line_high_color = "black"
        self.highlighted_irq_line = None
        self.irq_highlight_r = 3
        self.irq_circle_preview = None

        self.update()

        self.bind('<<DnDMoved>>', self.dnd_moved)
        self.bind('<<DnDDown>>', self.dnd_down)
        self.bind('<<DnDUp>>', self.dnd_up)
        self.dragged = []

        self.canvas.bind("<ButtonPress-3>", self.on_b3_press)
        self.canvas.bind("<ButtonRelease-3>", self.on_b3_release)

        # override super class method
        self.canvas.bind("<Motion>", self.motion_all)
        self.last_canvas_mouse = (0, 0)

        self.dragging_all = False
        self.all_were_dragged = False

        self.current_ph_iteration = None

        self.var_physical_layout = tk.BooleanVar()
        self.var_physical_layout.trace_variable("w",
            self.on_var_physical_layout)

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

        """
IRQ line creation

1.A) Right click on a device -> IRQ source:
    The device is marked as source end of new IRQ line.
1.B) Right click on single device -> IRQ source:
    The source end of new IRQ line is reseted. New value is last clicked
    device.
2) Right click on a device -> IRQ destination:
    The device is marked as destination end of new IRQ line. A new IRQ line is
    created with corresponding source and destination ends. Indexes are
    defaulted to 0 and names are defaulted no None (unnamed GPIO).
        """
        self.irq_src = None
        p.add_command(
            label = _("IRQ source"),
            command = self.on_popup_single_device_irq_source
        )
        self.irq_dst_cmd_idx = 1
        p.add_command(
            label = _("IRQ destination"),
            command = self.on_popup_single_device_irq_destination,
            state = "disabled"
        )

        p.add_command(
            label = _("Settings"),
            command = self.on_popup_single_device_settings
        )
        self.popup_single_device = p

        p = VarMenu(self.winfo_toplevel(), tearoff = 0)
        p.add_command(
            label = _("Add IRQ hub"),
            command = self.on_add_irq_hub 
        )
        p.add_checkbutton(
            label = _("Dynamic layout"),
            variable = self.var_physical_layout
        )
        self.popup_empty_no_selected = p

        p = VarMenu(self.winfo_toplevel(), tearoff = 0)
        p.add_command(
            label = _("Delete point"),
            command = self.on_popup_irq_line_delete_point
        )
        self.on_popup_irq_line_delete_point_idx = 0
        p.add_command(
            label = _("Settings"),
            command = self.on_popup_irq_line_settings
        )
        p.add_command(
            label = _("Delete"),
            command = self.on_popup_irq_line_delete
        )
        self.popup_irq_line = p

        # single IRQ hub popup menu 
        p = VarMenu(self.winfo_toplevel(), tearoff = 0)
        p.add_command(
            label = _("IRQ source"),
            command = self.on_popup_single_irq_hub_irq_source
        )
        self.popup_single_irq_hub_irq_dst_cmd_idx = 1
        p.add_command(
            label = _("IRQ destination"),
            command = self.on_popup_single_irq_hub_irq_destination,
            state = "disabled"
        )
        self.popup_single_irq_hub = p

        # single bus popup menu
        p = VarMenu(self.winfo_toplevel(), tearoff = 0)
        p.add_command(
            label = _("Settings"),
            command = self.on_popup_single_bus_settings
        )
        self.popup_single_bus = p

        self.current_popup = None

        self.mht.add_on_changed(self.on_machine_changed)

        self.ph_launch()

    def on_var_physical_layout(self, *args):
        if self.var_physical_layout.get():
            if not self.ph_is_running():
                self.__ph_launch__()
        elif self.ph_is_running():
            self.__ph_stop__()

    def on_machine_changed(self, op):
        if isinstance(op, MOp_SetDevQOMType):
            dev = self.mach.id2node[op.node_id]
            node = self.dev2node[dev]
            self.update_node_text(node)
        elif isinstance(op, MOp_SetDevParentBus):
            dev = self.mach.id2node[op.node_id]
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
        elif isinstance(op, MOp_AddIRQHub):
            # Assuming MOp_DelIRQHub is child class of MOp_AddIRQHub
            try:
                hub = self.mach.id2node[op.node_id]
            except KeyError: # removed
                for hub_node, hub in self.node2dev.iteritems():
                    if not isinstance(hub_node, IRQHubCircle):
                        continue
                    if hub in self.mach.irq_hubs:
                        continue
                    break

                self.circles.remove(hub_node)
                circle_id = self.node2id[hub_node]
                del self.node2id[hub_node]
                del self.id2node[circle_id]
                if circle_id in self.selected:
                    self.selected.remove(circle_id)
                    self.event_generate(MachineDiagramWidget.EVENT_SELECT)
                self.canvas.delete(circle_id)
                del self.dev2node[hub]
                del self.node2dev[hub_node]
            else:
                # added
                hub_node = IRQHubCircle(hub)

                self.dev2node[hub] = hub_node
                self.node2dev[hub_node] = hub

                self.add_irq_hub(hub_node)
        elif isinstance(op, MOp_DelIRQLine):
            # Assuming MOp_AddIRQLine is child class of MOp_DelIRQLine
            try:
                irq = self.mach.id2node[op.node_id]
            except KeyError:
                for line, irq in self.node2dev.iteritems():
                    if not (isinstance(line, IRQLine) \
                            and isinstance(irq, Node)):
                        continue
                    if not irq in self.mach.irqs:
                        break

                if line == self.highlighted_irq_line:
                    self.highlighted_irq_line = None
                    self.stop_circle_preview()

                for c in line.circles:
                    self.circles.remove(c)
                    if c == self.shown_irq_node:
                        self.canvas.delete(self.shown_irq_circle)
                        self.shown_irq_circle = None
                        self.shown_irq_node = None

                self.irq_lines.remove(line)

                self.canvas.delete(line.arrow)

                for line_id in line.lines:
                    self.canvas.delete(line_id)

                del self.node2dev[line]
                del self.dev2node[irq]
            else:
                src = self.dev2node[irq.src[0]]
                dst = self.dev2node[irq.dst[0]]

                irq_node = IRQLine(irq, src, dst)

                self.dev2node[irq] = irq_node
                self.node2dev[irq_node] = irq

                self.add_irq_line(irq_node)
        elif isinstance(op, MachineNodeSetLinkAttributeOperation):
            dev = self.mach.id2node[op.node_id]
            if isinstance(dev, QIRQLine):
                line = self.dev2node[dev]
                line.src = self.dev2node[dev.src_node]
                line.dst = self.dev2node[dev.dst_node]
        elif isinstance(op, MOp_SetChildBus):
            for bus_id in [ op.prev_bus_id, op.bus_id ]:
                if not bus_id == -1:
                    bus = self.mach.id2node[bus_id]
                    self.update_buslabel_text(self.dev2node[bus])

        self.invalidate()

    def on_popup_single_device_irq_source(self):
        sid = self.selected[0]
        self.irq_src = self.node2dev[self.id2node[sid]].id

        self.popup_single_device.entryconfig(
            self.irq_dst_cmd_idx,
            state = "normal"
        )
        self.popup_single_irq_hub.entryconfig(
            self.popup_single_irq_hub_irq_dst_cmd_idx,
            state = "normal"
        )

    def on_popup_single_device_irq_destination(self):
        did = self.selected[0]
        irq_dst = self.node2dev[self.id2node[did]].id

        self.mht.stage(
            MOp_AddIRQLine,
            self.irq_src, irq_dst,
            0, 0, None, None,
            self.mach.get_free_id()
        )
        self.mht.commit()

    def on_popup_single_irq_hub_irq_source(self):
        self.on_popup_single_device_irq_source()

    def on_popup_single_irq_hub_irq_destination(self):
        self.on_popup_single_device_irq_destination()

    def on_popup_single_device_settings(self):
        id = self.selected[0]

        x0, y0 = self.canvas.canvasx(0), self.canvas.canvasy(0)
        x, y = self.canvas.coords(id)[-2:]
        x = x - x0
        y = y - y0

        dev = self.node2dev[self.id2node[id]]
        wnd = DeviceSettingsWindow(self.mht, self, device = dev)

        geom = "+" + str(int(self.winfo_rootx() + x)) \
             + "+" + str(int(self.winfo_rooty() + y))

        wnd.geometry(geom)

    def on_popup_irq_line_delete_point(self):
        self.irq_line_delete_circle(*self.circle_to_be_deleted)
        self.invalidate()

    def on_popup_irq_line_settings(self):
        if not self.highlighted_irq_line:
            return

        p = self.current_popup

        wnd = IRQSettingsWindow(self.mht, self, irq = self.highlighted_irq_line)

        geom = "+" + str(int(p.winfo_rootx())) + "+" + str(int(p.winfo_rooty()))

        wnd.geometry(geom)

        # Allow highlighting of another lines when the command was done 
        self.current_popup.unpost()
        self.current_popup = None

    def on_popup_irq_line_delete(self):
        if not self.highlighted_irq_line:
            return

        irq = self.node2dev[self.highlighted_irq_line]
        self.mht.stage(MOp_DelIRQLine, irq.id)

        self.mht.commit()

        # the menu will be unposted after the command
        self.current_popup = None

    def on_popup_single_bus_settings(self):
        id = self.selected[0]

        x0, y0 = self.canvas.canvasx(0), self.canvas.canvasy(0)
        x, y = self.canvas.coords(id)[-2:]
        x = x - x0
        y = y - y0

        bus = self.node2dev[self.id2node[id]]
        wnd = BusSettingsWindow(bus, self.mht, self)

        geom = "+" + str(int(self.winfo_rootx() + x)) \
             + "+" + str(int(self.winfo_rooty() + y))

        wnd.geometry(geom)

    def on_add_irq_hub(self):
        p = self.current_popup
        x, y = p.winfo_rootx() - self.winfo_rootx() + self.canvas.canvasx(0), \
               p.winfo_rooty() - self.winfo_rooty() + self.canvas.canvasy(0)

        # print "Adding IRQ hub: " + str(x) + ", " + str(y)

        node_id = self.mach.get_free_id()

        self.mht.stage(MOp_AddIRQHub, node_id)
        self.mht.stage(MWOp_MoveNode, x, y, self, node_id)
        self.mht.commit()

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
                    self.event_generate(MachineDiagramWidget.EVENT_SELECT)
            return

        if not touched_ids:
            return

        if shift:
            for tid in touched_ids:
                if self.select_by_frame:
                    if not tid in self.selected:
                        self.selected.append(tid)
                        self.event_generate(MachineDiagramWidget.EVENT_SELECT)
                else:
                    if tid in self.selected:
                        self.selected.remove(tid)
                        self.event_generate(MachineDiagramWidget.EVENT_SELECT)
                    else:
                        self.selected.append(tid)
                        self.event_generate(MachineDiagramWidget.EVENT_SELECT)
        elif not self.selected == touched_ids:
            self.selected = list(touched_ids)
            self.event_generate(MachineDiagramWidget.EVENT_SELECT)

        self.invalidate()

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
                    self.event_generate(MachineDiagramWidget.EVENT_SELECT)
            else:
                if not tid in self.selected:
                    self.selected = [tid]
                    self.event_generate(MachineDiagramWidget.EVENT_SELECT)

            # touched node
            tnode = self.id2node[tid]

            if not tnode in self.node2dev:
                break

            # touched device, etc..
            if not self.current_popup:
                tdev = self.node2dev[tnode]

                if isinstance(tdev, DeviceNode):
                    if len(self.selected) == 1:
                        self.current_popup = self.popup_single_device
                elif isinstance(tdev, IRQHub):
                    if len(self.selected) == 1:
                        self.current_popup = self.popup_single_irq_hub
                elif isinstance(tdev, BusNode):
                    if len(self.selected) == 1:
                        self.current_popup = self.popup_single_bus

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
        self.all_were_dragged = False

    def on_b3_release(self, event):
        #print("on_b3_release")
        for n in self.nodes + self.buslabels + self.circles:
            n.static = False
        self.dragging_all = False
        self.master.config(cursor = "")

        if (not self.all_were_dragged) and self.highlighted_irq_line:
            if not self.current_popup:
                self.circle_to_be_deleted = None

                if self.shown_irq_circle:
                    for l in self.irq_lines:
                        for idx, c in enumerate(l.circles):
                            if c == self.shown_irq_node:
                                self.circle_to_be_deleted = (l, idx)
                                break
                        else:
                            continue
                        break

                self.popup_irq_line.entryconfig(
                    self.on_popup_irq_line_delete_point_idx,
                    state = "disabled" if self.circle_to_be_deleted is None \
                        else "normal"
                )

                x, y = self.canvas.canvasx(event.x), \
                       self.canvas.canvasy(event.y)

                self.current_popup = self.popup_irq_line

                try:
                    self.current_popup.tk_popup(event.x_root, event.y_root)
                    self.current_popup.grab_release()
                except:
                    self.current_popup.grab_release()
                    self.current_popup = None

                return

        if not (self.all_were_dragged or self.current_popup):
            if self.selected:
                self.selected = []
                self.event_generate(MachineDiagramWidget.EVENT_SELECT)

            x, y = self.canvas.canvasx(event.x), \
                   self.canvas.canvasy(event.y)

            if not self.canvas.find_overlapping(x - 3, y - 3, x + 3, y + 3):
                self.current_popup = self.popup_empty_no_selected

                try:
                    self.current_popup.tk_popup(event.x_root, event.y_root)
                    self.current_popup.grab_release()
                except:
                    self.current_popup.grab_release()
                    self.current_popup = None

    def motion_all(self, event):
        self.motion(event)
        #print("motion_all")

        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.last_canvas_mouse = x, y

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

        # If IRQ line popup menu is showed, then do not change IRQ highlighting
        if not self.current_popup == self.popup_irq_line:
            nearest = (None, sys.float_info.max)
            for irql in self.irq_lines:
                for seg_id in irql.lines:
                    x0, y0, x1, y1 = tuple(self.canvas.coords(seg_id))
                    v0 = Vector(x - x0, y - y0)
                    v1 = Vector(x - x1, y - y1)
                    v2 = Vector(x1 - x0, y1 - y0)
                    d = v0.Length() + v1.Length() - v2.Length()

                    if d < nearest[1]:
                        nearest = (irql, d)

            if self.highlighted_irq_line:
                self.highlight(self.highlighted_irq_line, False)
                self.highlighted_irq_line = None

            if nearest[1] <= self.irq_highlight_r:
                self.highlighted_irq_line = nearest[0]
                self.highlight(self.highlighted_irq_line, True)

                if self.shown_irq_circle:
                    self.canvas.lift(self.shown_irq_circle)

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
        self.invalidate()
        self.select_point = None
        self.canvas.delete(self.select_frame)
        self.select_frame = None
        self.all_were_dragged = True

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
                self.event_generate(MachineDiagramWidget.EVENT_SELECT)

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
        self.invalidate()
        self.select_point = None
        self.canvas.delete(self.select_frame)
        self.select_frame = None

    def dnd_down(self, event):
        id = self.canvas.find_withtag(tk.CURRENT)[0]

        if id == self.irq_circle_preview:
            self.circle_preview_to_irq(self.highlighted_irq_line)

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

            line = IRQLine(irq, src, dst)

            self.dev2node[irq] = line
            self.node2dev[line] = irq

            self.add_irq_line(line)

    def invalidate(self):
        if self.current_ph_iteration:
            self.current_ph_iteration = None

        if not "_ph_sync_single" in self.__dict__:
            self._ph_sync_single = self.after(0, self.ph_sync_single)

    def ph_iterate(self, t_limit_sec):
        if not self.current_ph_iteration:
            self.current_ph_iteration = self.ph_iterate_co()

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

    def ph_sync_single(self):
        self.ph_sync()
        del self._ph_sync_single

    def irq_circle_preview_update(self):
        if self.shown_irq_circle:
            if self.irq_circle_preview:
                self.canvas.delete(self.irq_circle_preview)
                self.irq_circle_preview = None
        else:
            x, y = self.last_canvas_mouse
            coords = [
                x - self.irq_circle_r, y - self.irq_circle_r,
                x + self.irq_circle_r, y + self.irq_circle_r
            ]
            if not self.irq_circle_preview:
                self.irq_circle_preview = self.canvas.create_oval(
                    *coords,
                    fill = "white",
                    tags = "DnD"
                )
                self.canvas.lift(self.irq_circle_preview)
            else:
                self.canvas.coords(self.irq_circle_preview, *coords)

        self._irq_circle_preview_update = self.after(10,
            self.irq_circle_preview_update)

    def start_circle_preview(self):
        self._irq_circle_preview_update = self.after(0,
            self.irq_circle_preview_update)

    def stop_circle_preview(self):
        if "_irq_circle_preview_update" in self.__dict__:
            self.after_cancel(self._irq_circle_preview_update)
            del self._irq_circle_preview_update
        if self.irq_circle_preview:
            self.canvas.delete(self.irq_circle_preview)
            self.irq_circle_preview = None

    def circle_preview_to_irq(self, irql):
        coords = self.canvas.coords(self.irq_circle_preview)
        x, y = (coords[0] + coords[2]) / 2, (coords[1] + coords[3]) / 2

        nearest = (0, sys.float_info.max)

        for idx, seg_id in enumerate(irql.lines):
            x0, y0, x1, y1 = tuple(self.canvas.coords(seg_id))
            v0 = Vector(x - x0, y - y0)
            v1 = Vector(x - x1, y - y1)
            v2 = Vector(x1 - x0, y1 - y0)
            d = v0.Length() + v1.Length() - v2.Length()

            if d < nearest[1]:
                nearest = (idx, d)

        self.shown_irq_node = self.irq_line_add_circle(irql, nearest[0], x, y)
        self.shown_irq_circle = self.irq_circle_preview

        self.irq_circle_preview = None
        self.stop_circle_preview()

    def process_irq_circles(self):
        total_circles = 0
        for l in self.irq_lines:
            total_circles += len(l.circles)

        if total_circles > self.irq_circle_total_limit:
            self.irq_circle_per_line_limit = int(self.irq_circle_total_limit /
                len(self.irq_lines))
            if self.irq_circle_per_line_limit == 0:
                self.irq_circle_per_line_limit = 1

            #print "Total circles: " + str(total_circles) + ", CPL: " + \
            #    str(self.irq_circle_per_line_limit)

        for l in self.irq_lines:
            self.ph_process_irq_line(l)

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

        self.process_irq_circles()

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

            if len(l.circles) < 2:
                continue

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

    def irq_line_add_circle(self, l, idx, x, y):
        c = IRQPathCircle()
        c.x, c.y = x - self.irq_circle_r, y - self.irq_circle_r
        c.r = self.irq_circle_r

        self.circles.append(c)

        id = self.canvas.create_line(
            0, 0, 1, 1,
            fill = self.irq_line_color
        )
        self.canvas.lower(id)

        l.circles.insert(idx, c)
        l.lines.insert(idx + 1, id)

        return c

    def irq_line_delete_circle(self, l, idx):
        self.canvas.delete(l.lines.pop(idx + 1))
        c = l.circles.pop(idx)

        if c == self.shown_irq_node:
            self.canvas.delete(self.shown_irq_circle)
            self.shown_irq_node = None
            self.shown_irq_circle = None

        self.circles.remove(c)

        return c

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
                    or self.irq_circle_per_line_limit <= line_circles
                ):
                dx = x1 - x0
                dy = y1 - y0
                d = math.sqrt( dx * dx + dy * dy )

                d1 = (self.irq_circle_r + self.irq_circle_s) * 2

                if d > 2 * d1:
                    x2 = (x0 + x1) / 2
                    y2 = (y0 + y1) / 2

                    self.irq_line_add_circle(l, i, x2, y2)

                    x1 = x2
                    y1 = y2

                    changed = True
                elif (    d < 1.5 * d1
                       or line_circles > self.irq_circle_per_line_limit
                    ):
                    if i < len(l.lines) - 1:
                        # not last line
                        self.irq_line_delete_circle(l, i)

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

    def ph_launch(self):
        self.var_physical_layout.set(True)

    def __ph_launch__(self):
        if "_ph_run" in self.__dict__:
            raise Exception("Attempt to launch physical simulation twice")
        self._ph_run = self.after(0, self.ph_run)

    def ph_is_running(self):
        return "_ph_run" in self.__dict__

    def ph_stop(self):
        self.var_physical_layout.set(False)

    def __ph_stop__(self):
        self.after_cancel(self._ph_run)
        del self._ph_run

    def ph_run(self):
        rest = self.ph_iterate(0.01)
        if rest < 0.001:
            rest = 0.001

        self._ph_run = self.after(int(rest * 1000), self.ph_run)

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

    def highlight(self, line, high = True):
        if high:
            color, layer_func, preview_func = self.irq_line_high_color, \
                self.canvas.lift, self.start_circle_preview
        else:
            color, layer_func, preview_func = self.irq_line_color, \
                self.canvas.lower, self.stop_circle_preview

        for seg_id in line.lines:
            self.canvas.itemconfig(seg_id, fill = color)
            layer_func(seg_id)

        self.canvas.itemconfig(line.arrow, fill = color)
        layer_func(line.arrow)

        preview_func()

    def add_bus(self, bus):
        id = self.canvas.create_line(
            0, 0, 0, 0
        )
        self.canvas.lower(id)

        self.id2node[id] = bus
        self.node2id[bus] = id

        self.buses.append(bus)

    def update_buslabel_text(self, bl):
        self.canvas.itemconfig(bl.text,
            text = bl.node.gen_child_name_for_bus()
        )

        t_bbox = self.canvas.bbox(bl.text)
        bl.text_width = t_bbox[2] - t_bbox[0]
        bl.text_height = t_bbox[3] - t_bbox[1]

        bl.width = bl.text_width + bl.padding
        bl.height = (1 + 2 * bl.cap_size) \
            * (bl.text_height + bl.padding)
        bl.offset = [bl.width / 2, 0]

    def add_buslabel(self, bl):
        node = BusLine(bl)
        self.add_bus(node)
        bl.busline = node

        id = self.canvas.create_text(
            bl.x, bl.y,
            state = tk.DISABLED
        )
        bl.text = id

        id = self.canvas.create_polygon(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            fill = "white",
            outline = "black",
            tag = "DnD"
        )

        self.update_buslabel_text(bl)

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

        irqs = {}
        for l in self.irq_lines:
            irqs[self.node2dev[l].id] = [
                (c.x + self.irq_circle_r, c.y + self.irq_circle_r) \
                    for c in l.circles
            ]

        layout[-1] = {
            "physical layout": self.var_physical_layout.get(),
            "IRQ lines points": irqs
        }

        return layout

    def SetLayout(self, l):
        layout_bak = self.GetLayout()
        try:
            for id, desc in l.iteritems():
                if id == -1:
                    try:
                        self.var_physical_layout.set(desc["physical layout"])
                    except KeyError:
                        pass

                    try:
                        irqs = desc["IRQ lines points"]
                    except KeyError:
                        irqs = {}

                    for irq_id, points in irqs.iteritems():
                        l = self.dev2node[self.mach.id2node[irq_id]]
                        while l.circles:
                            self.irq_line_delete_circle(l, 0)
                        for i, (x, y) in enumerate(points):
                            self.irq_line_add_circle(l, i, x, y)

                    continue
                dev = self.mach.id2node[id]
                if not dev:
                    continue
                n = self.dev2node[dev]
                n.x, n.y = desc[0], desc[1]

            self.invalidate()
        except:
            # if new layout is incorrect then restore previous one
            self.SetLayout(layout_bak)
