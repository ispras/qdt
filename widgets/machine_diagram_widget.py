__all__ = [
    "MIN_MESH_STEP"
  , "MAX_MESH_STEP"
  , "MachineDiagramWidget"
]

from .var_widgets import (
    VarMenu
)
from .DnDCanvas import (
    dragging_all,
    DRAG_GAP,
    CanvasDnD
)
from six import (
    text_type,
    binary_type
)
from six.moves import (
    reduce,
    range as xrange
)
from six.moves.tkinter import (
    StringVar,
    BooleanVar,
    DISABLED,
    ALL
)
from math import (
    sqrt,
    hypot
)
from random import (
    random
)
from time import (
    time
)
from sys import (
    float_info
)
from os import (
    remove
)
from os.path import (
    splitext
)
from common import (
    bidict,
    find_empty_aabb,
    PhBox,
    PhCircle,
    Vector,
    Segment,
    Polygon,
    mlget as _,
    sign
)
from qemu import (
    MOp_AddCPU,
    MOp_DelCPU,
    MOp_SetCPUAttr,
    CPUNode,
    MOp_SetBusAttr,
    MOp_AddDevice,
    MOp_DelDevice,
    MOp_AddBus,
    MOp_AddMemoryNode,
    MOp_DelBus,
    MOp_SetChildBus,
    BusNode,
    IRQLine as QIRQLine,
    MOp_SetNodeVarNameBase,
    MachineNodeSetLinkAttributeOperation,
    MOp_AddIRQLine,
    MOp_DelIRQLine,
    MOp_SetIRQAttr,
    MachineNodeOperation,
    MOp_AddIRQHub,
    MOp_SetDevParentBus,
    MOp_SetDevQOMType,
    Node,
    DeviceNode,
    IRQHub
)
from .device_settings_window import (
    DeviceSettingsWindow
)
from .irq_settings import (
    IRQSettingsWindow
)
from .bus_settings import (
    BusSettingsWindow
)
from .cpu_settings import (
    CPUSettingsWindow
)
from .popup_helper import (
    TkPopupHelper
)
from .cross_dialogs import (
    asksaveas
)
from six.moves.tkinter_messagebox import (
    showerror
)
from .hotkey import (
    HotKeyBinding
)
from canvas2svg import (
    configure as svg_configure,
    SEGMENT_TO_PATH,
    saveall as saveall2svg
)
from .irq_hub_settings import (
    IRQHubSettingsWindow
)
from itertools import (
    count
)

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

    def _backup(self):
        w = self.get_widget_descriptor()

        self.orig = w.x, w.y

    def _do(self):
        w = self.get_widget_descriptor()

        w.x, w.y = self.tgt

    def _undo(self):
        w = self.get_widget_descriptor()

        w.x, w.y = self.orig

    def __write_set__(self):
        return MachineWidgetNodeOperation.__write_set__(self) + [
            self.get_widget_entry()
        ]


class TextBox(PhBox):

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
        self.bus_labels = []

    def get_bind_point(self, target):
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


class BusLine(PhBox):

    def __init__(self, bl):
        PhBox.__init__(self,
            w = 1,
            h = 50 * 2,
        )
        self.extra_length = 50

        self.buslabel = bl


class BusLabel(TextBox):

    def __init__(self, bus):
        TextBox.__init__(self, bus)

        self.cap_size = 0.5
        self.busline = None

class ConnectionLine(PhBox):

    def __init__(self, dev_node, bus_node):
        PhBox.__init__(self, h = 1)
        self.dev_node = dev_node
        self.bus_node = bus_node

        self.update()

    def update(self):
        self.y = self.dev_node.y + self.dev_node.height / 2
        self.x = min([
            self.bus_node.x,
            self.dev_node.x + self.dev_node.width / 2
        ])
        self.width = max([
            self.bus_node.x,
            self.dev_node.x + self.dev_node.width / 2
        ]) - self.x


class NodeCircle(PhCircle):

    def __init__(self):
        PhCircle.__init__(self,
            spacing = 0
        )
        self.offset = [0, 0]


class IRQPathCircle(NodeCircle):

    def __init__(self, line):
        NodeCircle.__init__(self)
        self.line = line


class IRQHubCircle(NodeCircle):

    def __init__(self, hub):
        NodeCircle.__init__(self)
        self.spacing = 5
        self.node = hub

    def get_bind_point(self, target):
        if target:
            dx = target[0] - self.x
            dy = target[1] - self.y
            d = sqrt( dx * dx + dy * dy )
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


# limitation of the mesh drawing algorithm
MIN_MESH_STEP = 1
# limitation of Canvas.create_line.dash
MAX_MESH_STEP = 260

LAYOUT_SHOW_MESH = "show mesh"
LAYOUT_MESH_STEP = "mesh step"
LAYOUT_DYNAMIC = "physical layout" # this name difference is a legacy issue
LAYOUT_IRQ_LINES_POINTS = "IRQ lines points"


# MachineDiagramWidget states, use them with `is` operator only
# They do extends CanvasDnD states list
rect_selecting = object()


class MachineDiagramWidget(CanvasDnD, TkPopupHelper):
    EVENT_SELECT = "<<Select>>"

    def __init__(self, parent, mach_desc, node_font = None, readonly = False):
        CanvasDnD.__init__(self, parent,
            id_priority_sort_function = self.sort_ids_by_priority
        )
        TkPopupHelper.__init__(self)

        if node_font is None:
            self.node_font = ("Monospace", 10)
        else:
            self.node_font = node_font

        mach_desc.link(handle_system_bus = False)

        self.mach = mach_desc

        toplevel = self.winfo_toplevel()
        try:
            self.task_manager = toplevel.task_manager
        except:
            self.task_manager = None

        try:
            self.hk = hotkeys = toplevel.hk
        except AttributeError:
            self.hk = hotkeys = None
        else:
            self.bindings = [
                HotKeyBinding(
                    self.__switch_show_mesh,
                    key_code = 58,
                    description = _("Show/hide mesh."),
                    symbol = "M"
                ),
                HotKeyBinding(
                    self.on_export_diagram,
                    key_code = 26,
                    description = _("Export of machine diagram."),
                    symbol = "E"
                ),
                HotKeyBinding(
                    self.on_diagram_finding,
                    key_code = 41,
                    description = _("Finding of machine diagram."),
                    symbol = "F"
                ),
                HotKeyBinding(
                    self.on_diagram_centering,
                    key_code = 54,
                    description = _("Centering of machine diagram."),
                    symbol = "C"
                )
            ]
            hotkeys.add_bindings(self.bindings)

        try:
            pht = self.winfo_toplevel().pht
        except AttributeError:
            mht = None
        else:
            if pht is None:
                mht = None
            else:
                mht = pht.get_machine_proxy(self.mach)

        # snapshot mode without MHT
        if mht is not None:
            mht.watch_changed(self.on_machine_changed)

            if readonly:
                # In read-only mode user may not change the machine while inner
                # changes still must be watched.
                mht = None

        self.mht = mht

        self.id2node = bidict()
        self.node2id = self.id2node.mirror
        self.dev2node = {}
        self.node2dev = {}
        self.node2idtext = {}

        self.bind(MachineDiagramWidget.EVENT_SELECT, self.on_select, "+")
        self.ids_shown_on_select = set([])

        self.nodes = []
        self.buslabels = []
        self.buses = []
        self.conns = []
        self.circles = []
        self.irq_lines = []

        self.velocity_k = 0.05
        self.velocity_limit = 10

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

        # the cache with VarString of node variable names
        self.mach.node_id2var_name = {}
        self.__update_var_names()

        self.bind('<<DnDMoved>>', self.dnd_moved, "+")
        self.bind('<<DnDDown>>', self.dnd_down, "+")
        self.bind('<<DnDUp>>', self.dnd_up, "+")
        self.bind("<<DnDAll>>", self.dnd_all, "+")
        self.bind("<<DnDAllMoved>>", self.dnd_all_moved, "+")
        self.bind("<<DnDAllUp>>", self.dnd_all_up, "+")
        self.dragged = []
        # A canvas ID is considered "touched" since "<<DnDDown>>" and
        # until "<<DnDMoved>>".
        self.touched = None

        # User may press Shift + RMB to remove IRQ line point.
        # In that case, DnDCanvas should not begin drag all sequence.
        # So, we override DnDCanvas's <ButtonPress-3> handler there and call
        # it from `on_b3_press` when necessary.
        self.bind("<ButtonPress-3>", self.on_b3_press)
        self.all_were_dragged = False
        self.bind("<ButtonRelease-3>", self.on_b3_release, "+")

        self.bind("<Double-Button-1>", self.on_b1_double, "+")

        self.bind("<Motion>", self.motion_all, "+")
        self.last_canvas_mouse = (0, 0)

        self.display_mesh = False
        self.bind("<Configure>", self.__on_resize, "+")

        if self.mesh_step.get() > MAX_MESH_STEP:
            self.mesh_step.set(MAX_MESH_STEP)
        elif self.mesh_step.get() < MIN_MESH_STEP:
            self.mesh_step.set(MIN_MESH_STEP)
        self.mesh_step.trace_variable("w", self.__on_mesh_step)

        self.current_ph_iteration = None

        self.var_physical_layout = BooleanVar()
        self.var_physical_layout.trace_variable("w",
            self.on_var_physical_layout)

        self.selection_marks = []
        self.selection_mark_color = "orange"
        self.selected = []
        self.bind("<ButtonPress-1>", self.on_b1_press, "+")
        self.bind("<ButtonRelease-1>", self.on_b1_release, "+")

        self.select_frame = None
        self.select_frame_color = "green"

        self.key_state = {}
        self.bind("<KeyPress>", self.on_key_press, "+")
        self.bind("<KeyRelease>", self.on_key_release, "+")
        self.focus_set()

        self.bind("<Delete>", self.on_key_delete, "+")

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
        p.add_separator()
        p.add_command(
            label = _("Clone"),
            command = self.on_popup_single_device_clone,
        )
        p.add_separator()
        p.add_command(
            label = _("Settings"),
            command = self.on_popup_single_device_settings
        )
        p.add_separator()
        p.add_command(
            label = _("Delete"),
            command = self.notify_popup_command if self.mht is None else \
               self.on_popup_single_device_delete
        )
        self.popup_single_device = p

        p = VarMenu(self.winfo_toplevel(), tearoff = 0)
        p.add_command(
            label = _("Add IRQ hub"),
            command = self.notify_popup_command if self.mht is None else \
                self.on_add_irq_hub
        )

        p.add_command(
            label = _("Add CPU"),
            command = self.notify_popup_command if self.mht is None else \
                self.on_add_cpu
        )

        p0 = VarMenu(p, tearoff = 0)
        for device_type in [
            _("Common device"),
            _("System bus device"),
            _("PCI-E function")
        ]:
            p0.add_command(
                label = device_type,
                command = self.notify_popup_command if self.mht is None else \
                    getattr(self, "on_add_" +
                        device_type.key_value.lower().replace(" ", "_").\
                            replace("-", "_")
                )
            )
        p.add_cascade(
            label = _("Add device"),
            menu = p0
        )

        p0 = VarMenu(p, tearoff = 0)
        for bus_type in [
            "Common",
            "System",
            "PCI-E",
            "ISA",
            "IDE",
            "I2C"
        ]:
            p0.add_command(
                label = _(bus_type),
                command = self.notify_popup_command if self.mht is None else \
                    getattr(self, "on_add_bus_" +
                        bus_type.lower().replace(" ", "_").replace("-", "_")
                )
            )
        p.add_cascade(
            label = _("Add bus"),
            menu = p0
        )
        p.add_separator()
        p.add_checkbutton(
            label = _("Dynamic layout"),
            variable = self.var_physical_layout
        )

        export_args = {
            "label" : _("Export diagram"),
            "command" : self.on_export_diagram
        }
        if hotkeys is not None:
            export_args["accelerator"] = \
                hotkeys.get_keycode_string(self.on_export_diagram)
        p.add_command(**export_args)

        find_args = {
            "label" : _("Diagram finding"),
            "command" : self.on_diagram_finding
        }
        if hotkeys is not None:
            find_args["accelerator"] = \
                hotkeys.get_keycode_string(self.on_diagram_finding)
        p.add_command(**find_args)

        centering_args = {
            "label" : _("Diagram centering"),
            "command" : self.on_diagram_centering
        }
        if hotkeys is not None:
            centering_args["accelerator"] = \
                hotkeys.get_keycode_string(self.on_diagram_centering)
        p.add_command(**centering_args)

        self.var_show_mesh = BooleanVar()
        self.var_show_mesh.trace_variable("w", self.__on_show_mesh)
        show_mesh_args = {
            "label": _("Show mesh"),
            "variable": self.var_show_mesh
        }
        if hotkeys is not None:
            show_mesh_args["accelerator"] = hotkeys.get_keycode_string(
                self.__switch_show_mesh
            )
        p.add_checkbutton(**show_mesh_args)

        self.popup_empty_no_selected = p

        p = VarMenu(self.winfo_toplevel(), tearoff = 0)
        p.add_command(
            label = _("Delete point"),
            command = self.on_popup_irq_line_delete_point
        )
        self.on_popup_irq_line_delete_point_idx = 0
        p.add_separator()
        p.add_command(
            label = _("Settings"),
            command = self.on_popup_irq_line_settings
        )
        p.add_separator()
        p.add_command(
            label = _("Delete"),
            command = self.notify_popup_command if self.mht is None else \
                self.on_popup_irq_line_delete
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
            command = self.notify_popup_command if self.mht is None else \
                self.on_popup_single_irq_hub_irq_destination,
            state = "disabled"
        )
        p.add_separator()
        p.add_command(
            label = _("Settings"),
            command = self.on_popup_irq_hub_settings
        )
        p.add_separator()
        p.add_command(
            label = _("Delete"),
            command = self.notify_popup_command if self.mht is None else \
                self.on_popup_single_irq_hub_delete
        )
        self.popup_single_irq_hub = p

        # single bus popup menu
        p = VarMenu(self.winfo_toplevel(), tearoff = 0)
        p.add_command(
            label = _("Settings"),
            command = self.on_popup_single_bus_settings
        )
        p.add_separator()
        p.add_command(
            label = _("Delete"),
            command = self.notify_popup_command if self.mht is None else \
                self.on_popup_single_bus_delete
        )
        self.popup_single_bus = p

        # single CPU popup menu
        p = VarMenu(self.winfo_toplevel(), tearoff = 0)
        p.add_command(
            label = _("Settings"),
            command = self.on_popup_single_cpu_settings
        )
        p.add_separator()
        p.add_command(
            label = _("Delete"),
            command = self.notify_popup_command if self.mht is None else \
                self.on_popup_single_cpu_delete
        )
        self.popup_single_cpu = p

        # popup menu for multiple selection
        p = VarMenu(self.winfo_toplevel(), tearoff = 0)
        p.add_command(
            label = _("Delete"),
            command = self.notify_popup_command if self.mht is None else \
                self.on_popup_multiple_delete
        )
        self.popup_multiple = p

        if hotkeys is not None:
            # focus handlers do only managing hotkeys
            self.bind("<FocusIn>", self.__on_focus_in__, "+")
            self.bind("<FocusOut>", self.__on_focus_out__, "+")

        self.bind("<Destroy>", self.__on_destroy__, "+")

        self.ph_launch()

    def on_b1_double(self, event):
        """ Double-click handler for 1-st (left) mouse button. """

        x, y = self.canvasx(event.x), self.canvasy(event.y)
        touched_ids = self.find_overlapping(x - 3, y - 3, x + 3, y + 3)

        if self.highlighted_irq_line:
            touched_ids += (self.highlighted_irq_line.arrow,)

        touched_ids = self.sort_ids_by_priority(touched_ids)

        for tid in touched_ids:
            if tid == self.shown_irq_circle:
                # special lookup for IRQ lines
                tnode = self.shown_irq_node.line
            else:
                try:
                    # touched node
                    tnode = self.id2node[tid]
                except KeyError:
                    continue

            try:
                # touched device, etc..
                tdev = self.node2dev[tnode]
            except KeyError:
                continue

            # Handler must perform machine node specific action for
            # double-click.
            handler = None

            if isinstance(tdev, DeviceNode):
                handler = self.show_device_settings
            elif isinstance(tdev, BusNode):
                handler = self.show_bus_settings
            elif isinstance(tdev, QIRQLine):
                handler = self.show_irq_line_settings
            elif isinstance(tdev, IRQHub):
                handler = self.show_irq_hub_settings
            elif isinstance(tdev, CPUNode):
                handler = self.show_cpu_settings

            if handler is None:
                continue

            x0, y0 = self.canvasx(0), self.canvasy(0)
            x, y = self.coords(tid)[-2:]
            x = x - x0
            y = y - y0

            handler(tdev, x, y)
            break

    def __on_focus_in__(self, *args, **kw):
        for binding in self.bindings:
            binding.enabled = True

    def __on_focus_out__(self, *args, **kw):
        for binding in self.bindings:
            binding.enabled = False

    def __on_destroy__(self, *args, **kw):
        self.var_physical_layout.set(False)
        if self.mht is not None:
            # the listener is not assigned in snapshot mode
            self.mht.unwatch_changed(self.on_machine_changed)

        try:
            self.after_cancel(self._update_selection_marks_onece)
        except AttributeError:
            pass

        if self.hk:
            self.hk.delete_bindings(self.bindings)

    def on_export_diagram(self, *args):
        file_name = asksaveas(self,
            [
                ((_("Scalable Vector Graphics image"), ".svg")),
                ((_("Postscript image"), ".ps"))
            ],
            title = _("Export machine diagram")
        )

        if not file_name:
            return

        try:
            open(file_name, "wb").close()
        except IOError as e:
            if not e.errno == 13: # Do not remove read-only files
                try:
                    remove(file_name)
                except:
                    pass

            showerror(
                title = _("Cannot export image").get(),
                message = str(e)
            )
            return

        ext = splitext(file_name)[1]

        if ext == ".ps":
            self.postscript(file = file_name, colormode = "color")

            # fix up font
            f = open(file_name, "rb")
            lines = f.readlines()
            f.close()
            remove(file_name)

            f = open(file_name, "wb")
            for l in lines:
                f.write(l.replace("/DejavuSansMono", "/" + self.node_font[0]))
            f.close()
        elif ext == ".svg":
            svg_configure(SEGMENT_TO_PATH)
            saveall2svg(file_name, self)
        else:
            showerror(
                title = _("Export error").get(),
                message = (_("Unexpected file extension %s") % ext).get()
            )

    def on_diagram_finding(self, *args):
        # Disabled when user doing something with mouse
        if self._state is not None:
            return

        ids = self.find_withtag("DnD")
        if len(ids) == 0:
            return

        sx = self.canvasx(self.winfo_width() / 2)
        sy = self.canvasy(self.winfo_height() / 2)

        bboxes = map(lambda _id: self.bbox(_id), ids)
        centers = map(lambda b: ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), bboxes)
        x0, y0 = min(centers, key = lambda a: hypot(a[0] - sx, a[1] - sy))

        x = self.canvasx(0) + self.winfo_width() / 2 - x0
        y = self.canvasy(0) + self.winfo_height() / 2 - y0

        self.scan_mark(0, 0)
        self.scan_dragto(int(x), int(y), gain = 1)

        # cancel current physic iteration if moved
        self.invalidate()

        self.__repaint_mesh()

    def on_diagram_centering(self, *args):
        # Disabled when user doing something with mouse
        if self._state is not None:
            return

        ids = self.find_withtag("DnD")
        if len(ids) == 0:
            return

        x1, y1, x2, y2 = reduce(
            lambda a, b: (
                min(a[0], b[0]), min(a[1], b[1]),
                max(a[2], b[2]), max(a[3], b[3])
            ),
            map(lambda _id: self.bbox(_id), ids)
        )

        x = self.canvasx(0) + self.winfo_width() / 2 - (x1 + x2) / 2
        y = self.canvasy(0) + self.winfo_height() / 2 - (y1 + y2) / 2

        self.scan_mark(0, 0)
        self.scan_dragto(int(x), int(y), gain = 1)

        # cancel current physic iteration if moved
        self.invalidate()

        self.__repaint_mesh()

    def on_var_physical_layout(self, *args):
        if self.var_physical_layout.get():
            if not self.ph_is_running():
                self.__ph_launch__()
        elif self.ph_is_running():
            self.__ph_stop__()

    def hide_irq_line_circle(self):
        self.delete(self.shown_irq_circle)
        self.shown_irq_circle = None
        self.shown_irq_node = None

    def __line_and_node_idx_of_shown_irq_circle(self):
        shown_irq_node = self.shown_irq_node

        for l in self.irq_lines:
            for idx, c in enumerate(l.circles):
                if c is shown_irq_node:
                    return (l, idx)

        raise RuntimeError("Cannot lookup line and node index for shown circle")

    def on_machine_changed(self, op):
        if not isinstance(op, MachineNodeOperation):
            return

        if op.sn != self.mach.__sn__:
            return

        if (isinstance(op, MOp_SetDevQOMType) or
            isinstance(op, MOp_SetCPUAttr) and op.attr == "qom_type"
        ):
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
                    conn_id = self.node2id.pop(node.conn)
                    self.conns.remove(node.conn)
                    self.delete(conn_id)
                    node.conn = None
            else:
                pbn = self.dev2node[pb].busline
                self.add_conn(node, pbn)

        elif isinstance(op, MOp_AddIRQHub):
            # Assuming MOp_DelIRQHub is child class of MOp_AddIRQHub
            try:
                hub = self.mach.id2node[op.node_id]
            except KeyError: # removed
                for hub_node, hub in self.node2dev.items():
                    if not isinstance(hub_node, IRQHubCircle):
                        continue
                    if hub in self.mach.irq_hubs:
                        continue
                    break

                self.circles.remove(hub_node)
                circle_id = self.node2id.pop(hub_node)
                if circle_id in self.selected:
                    self.selected.remove(circle_id)
                    self.event_generate(MachineDiagramWidget.EVENT_SELECT)
                self.delete(circle_id)
                del self.dev2node[hub]
                del self.node2dev[hub_node]

                if self.irq_src == op.node_id:
                    self.irq_src = None
                    self.__set_irq_dst_cmd_enabled(False)
            else:
                # added
                hub_node = IRQHubCircle(hub)

                self.dev2node[hub] = hub_node
                self.node2dev[hub_node] = hub

                self.add_irq_hub(hub_node)

            self.__update_var_names()

        elif isinstance(op, MOp_DelIRQLine):
            # Assuming MOp_AddIRQLine is child class of MOp_DelIRQLine
            try:
                irq = self.mach.id2node[op.node_id]
            except KeyError:
                for line, irq in self.node2dev.items():
                    if not (isinstance(line, IRQLine)
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
                        self.hide_irq_line_circle()

                self.irq_lines.remove(line)

                self.delete(line.arrow)

                for line_id in line.lines:
                    self.delete(line_id)

                del self.node2dev[line]
                del self.dev2node[irq]

                del self.node2id[line]
            else:
                src = self.dev2node[irq.src[0]]
                dst = self.dev2node[irq.dst[0]]

                irq_node = IRQLine(irq, src, dst)

                self.dev2node[irq] = irq_node
                self.node2dev[irq_node] = irq

                self.add_irq_line(irq_node)

            self.__update_var_names()

        elif isinstance(op, MachineNodeSetLinkAttributeOperation):
            dev = self.mach.id2node[op.node_id]
            if isinstance(dev, QIRQLine):
                line = self.dev2node[dev]
                line.src = self.dev2node[dev.src_node]
                line.dst = self.dev2node[dev.dst_node]

        elif isinstance(op, MOp_SetBusAttr):
            if op.attr in ["child_name", "force_index"]:
                bus = self.mach.id2node[op.node_id]
                self.update_buslabel_text(self.dev2node[bus])

        elif isinstance(op, MOp_SetChildBus):
            dev = self.mach.id2node[op.node_id]
            dev_wgt = self.dev2node[dev]
            dev_node_id = self.node2id[dev_wgt]

            if dev.buses:
                self.addtag_withtag("fixed_x", dev_node_id)
            else:
                self.dtag(dev_node_id, "fixed_x")

            for bus_id in (
                [ b.id for b in dev.buses ] + [ op.prev_bus_id, op.bus_id ]
            ):
                if not bus_id == -1:
                    bus = self.mach.id2node[bus_id]
                    self.update_buslabel_text(self.dev2node[bus])

            dev_wgt.bus_labels = [self.dev2node[bus] for bus in dev.buses]

        elif isinstance(op, MOp_AddBus) or isinstance(op, MOp_DelBus):
            try:
                bus = self.mach.id2node[op.node_id]
            except KeyError:
                # deleted
                for bus, bl in self.dev2node.items():
                    if isinstance(bus, BusNode):
                        if bus.id == -1:
                            break

                poly_id = self.node2id.pop(bl)
                line_id = self.node2id.pop(bl.busline)

                if poly_id in self.selected:
                    self.selected.remove(poly_id)
                    self.event_generate(MachineDiagramWidget.EVENT_SELECT)

                self.buslabels.remove(bl)

                self.delete(poly_id)
                self.delete(bl.text)

                self.buses.remove(bl.busline)

                self.delete(line_id)

                del self.dev2node[bus]
                del self.node2dev[bl]
            else:
                # added
                node = BusLabel(bus)

                self.dev2node[bus] = node
                self.node2dev[node] = bus

                self.add_buslabel(node)

            self.__update_var_names()

        elif isinstance(op, MOp_AddDevice) or isinstance(op, MOp_DelDevice):
            try:
                dev = self.mach.id2node[op.node_id]
            except KeyError:
                # deleted
                for dev, node in self.dev2node.items():
                    if isinstance(dev, DeviceNode):
                        if dev.id == -1:
                            break

                node_id = self.node2id.pop(node)

                if node_id in self.selected:
                    self.selected.remove(node_id)
                    self.event_generate(MachineDiagramWidget.EVENT_SELECT)

                self.nodes.remove(node)
                self.delete(node_id)
                self.delete(node.text)
                del self.dev2node[dev]
                del self.node2dev[node]

                if self.irq_src == op.node_id:
                    self.irq_src = None
                    self.__set_irq_dst_cmd_enabled(False)
            else:
                # added
                node = TextBox(dev)

                self.dev2node[dev] = node
                self.node2dev[node] = dev

                self.add_node(node, None)

            self.__update_var_names()

        elif isinstance(op, (MOp_AddCPU, MOp_DelCPU)):
            try:
                cpu = self.mach.id2node[op.node_id]
            except KeyError:
                # deleted
                for cpu, node in self.dev2node.items():
                    if isinstance(cpu, CPUNode):
                        if cpu.id == -1:
                            break

                node_id = self.node2id.pop(node)

                if node_id in self.selected:
                    self.selected.remove(node_id)
                    self.event_generate(MachineDiagramWidget.EVENT_SELECT)

                self.nodes.remove(node)
                self.delete(node_id)
                self.delete(node.text)
                del self.dev2node[cpu]
                del self.node2dev[node]
            else:
                # added
                node = TextBox(cpu)

                self.dev2node[cpu] = node
                self.node2dev[node] = cpu

                self.add_node(node, None)

            self.__update_var_names()

        elif isinstance(op, MOp_SetNodeVarNameBase):
            self.__update_var_names()

        elif isinstance(op, MOp_AddMemoryNode):
            self.__update_var_names()

        self.invalidate()

    def __set_irq_dst_cmd_enabled(self, value):
        state = "normal" if value else DISABLED

        self.popup_single_device.entryconfig(
            self.irq_dst_cmd_idx,
            state = state
        )
        self.popup_single_irq_hub.entryconfig(
            self.popup_single_irq_hub_irq_dst_cmd_idx,
            state = state
        )

    def on_popup_single_device_irq_source(self):
        sid = self.current_popup_tag
        self.irq_src = self.node2dev[self.id2node[sid]].id

        self.__set_irq_dst_cmd_enabled(True)

        self.notify_popup_command()

    def on_popup_single_device_irq_destination(self):
        irq_src = self.irq_src

        did = self.current_popup_tag
        irq_dst = self.node2dev[self.id2node[did]].id

        irq_id = self.mach.get_free_id()

        self.mht.stage(
            MOp_AddIRQLine,
            irq_src, irq_dst,
            0, 0, None, None,
            irq_id
        )

        # auto set GPIO names and indices at the ends of that new IRQ line
        project = self.mht.pht.p
        qom_tree = project.qom_tree

        for node_id, prefix in [
            (irq_src, "src"),
            (irq_dst, "dst")
        ]:
            node = self.mach.id2node[node_id]
            if not isinstance(node, DeviceNode):
                continue

            gpio_name = None
            attr_name = prefix + "_irq_name"

            if qom_tree is not None: # cannot choice GPIO name without QOM tree
                name = node.qom_type

                # try to find such type in tree
                for t in next(qom_tree.find(name = "device")).descendants():
                    if name == t.name:
                        break
                    try:
                        if name in t.macro:
                            break
                    except AttributeError:
                        pass
                else:
                    t = None

                # try to find GPIO names for this type
                while t:
                    try:
                        if prefix == "src":
                            gpios = t.out_gpio_names
                        else:
                            gpios = t.in_gpio_names
                    except AttributeError:
                        pass
                    else:
                        if gpios:
                            gpio_name = gpios[0]
                            # a GPIO name is found, assign it
                            self.mht.stage(MOp_SetIRQAttr, attr_name,
                                gpio_name, irq_id
                            )
                            break

                    t = t.parent

            # find and assign free GPIO index
            attr_dev = prefix + "_dev"
            attr_idx = prefix + "_irq_idx"
            for idx in count(0):
                for irq in node.irqs:
                    if getattr(irq, attr_dev) is not node:
                        continue # opposite IRQ direction
                    if getattr(irq, attr_name) != gpio_name:
                        continue # other GPIO name
                    if idx == getattr(irq, attr_idx):
                        break
                else:
                    # free idx found, assign it
                    if idx != 0: # default value
                        self.mht.stage(MOp_SetIRQAttr, attr_idx, idx, irq_id)
                    break
                # this idx is already used

        self.mht.commit(sequence_description = _("Add IRQ line."))

        self.notify_popup_command()

    def show_irq_hub_settings(self, hub, x, y):
        wnd = IRQHubSettingsWindow(self,
            node = hub,
            machine = self.mach,
            machine_history_tracker = self.mht,
        )

        geom = "+" + str(int(self.winfo_rootx() + x)) \
             + "+" + str(int(self.winfo_rooty() + y))

        wnd.geometry(geom)

    def on_popup_irq_hub_settings(self):
        _id = self.current_popup_tag

        x0, y0 = self.canvasx(0), self.canvasy(0)
        x, y = self.coords(_id)[-2:]
        x = x - x0
        y = y - y0

        hub = self.node2dev[self.id2node[_id]]

        self.show_irq_hub_settings(hub, x, y)

        self.notify_popup_command()

    def on_popup_single_irq_hub_irq_source(self):
        self.on_popup_single_device_irq_source()

    def on_popup_single_irq_hub_irq_destination(self):
        self.on_popup_single_device_irq_destination()

    def on_popup_single_irq_hub_delete(self):
        hid = self.current_popup_tag
        node = self.id2node[hid]
        hid = self.node2dev[node].id

        if node.x != 0 or node.y != 0:
            # move node to 0, 0 to preserve its coordinates
            self.mht.stage(MWOp_MoveNode, 0, 0, self, hid)

        self.mht.delete_irq_hub(hid)
        self.mht.commit()

        self.notify_popup_command()

    def on_popup_single_device_delete(self):
        dev_id = self.current_popup_tag
        node = self.id2node[dev_id]
        dev_id = self.node2dev[node].id

        if node.x != 0 or node.y != 0:
            # move node to 0, 0 to preserve its coordinates
            self.mht.stage(MWOp_MoveNode, 0, 0, self, dev_id)

        self.mht.delete_device(dev_id)
        self.mht.commit()

        self.notify_popup_command()

    def show_device_settings(self, device, x, y):
        wnd = DeviceSettingsWindow(self,
            machine = self.mach,
            machine_history_tracker = self.mht,
            device = device,
        )

        geom = "+" + str(int(self.winfo_rootx() + x)) \
             + "+" + str(int(self.winfo_rooty() + y))

        wnd.geometry(geom)

    def on_popup_single_device_clone(self):
        dev_id = self.current_popup_tag
        node = self.id2node[dev_id]
        dev_id = self.node2dev[node].id

        x, y = self.find_space_near(
            node.x, node.y, node.width, node.height, node.spacing
        )

        new_id = self.mht.clone_device(dev_id)
        self.mht.stage(MWOp_MoveNode, x, y, self, new_id)
        self.mht.commit()

        self.notify_popup_command()

    def on_popup_single_device_settings(self):
        _id = self.current_popup_tag

        x0, y0 = self.canvasx(0), self.canvasy(0)
        x, y = self.coords(_id)[-2:]
        x = x - x0
        y = y - y0

        dev = self.node2dev[self.id2node[_id]]

        self.show_device_settings(dev, x, y)

        self.notify_popup_command()

    def on_popup_irq_line_delete_point(self):
        self.irq_line_delete_circle(*self.circle_to_be_deleted)
        self.invalidate()

        self.notify_popup_command()

    def show_irq_line_settings(self, irq, x, y):
        wnd = IRQSettingsWindow(self,
            machine = self.mach,
            machine_history_tracker = self.mht,
            irq = irq,
        )

        geom = "+" + str(int(self.winfo_rootx() + x)) \
             + "+" + str(int(self.winfo_rooty() + y))

        wnd.geometry(geom)

    def on_popup_irq_line_settings(self):
        if not self.highlighted_irq_line:
            self.notify_popup_command()
            return

        self.show_irq_line_settings(self.node2dev[self.highlighted_irq_line],
            self.popup_x - self.winfo_rootx(),
            self.popup_y - self.winfo_rooty()
        )

        # Allow highlighting of another lines when the command was done 
        self.notify_popup_command()

    def on_popup_irq_line_delete(self):
        if not self.highlighted_irq_line:
            self.notify_popup_command()
            return

        irq = self.node2dev[self.highlighted_irq_line]
        self.mht.delete_irq_line(irq.id)

        self.mht.commit()

        # the menu will be unposted after the command
        self.notify_popup_command()

    def show_bus_settings(self, bus, x, y):
        wnd = BusSettingsWindow(self,
            bus = bus,
            machine = self.mach,
            machine_history_tracker = self.mht,
        )

        geom = "+" + str(int(self.winfo_rootx() + x)) \
             + "+" + str(int(self.winfo_rooty() + y))

        wnd.geometry(geom)

    def on_popup_single_bus_settings(self):
        _id = self.current_popup_tag

        x0, y0 = self.canvasx(0), self.canvasy(0)
        x, y = self.coords(_id)[-2:]
        x = x - x0
        y = y - y0

        bus = self.node2dev[self.id2node[_id]]

        self.show_bus_settings(bus, x, y)

        self.notify_popup_command()

    def on_popup_single_bus_delete(self):
        bus_id = self.current_popup_tag
        node = self.id2node[bus_id]
        bus_id = self.node2dev[node].id

        if node.x != 0 or node.y != 0:
            # move node to 0, 0 to preserve its coordinates
            self.mht.stage(MWOp_MoveNode, 0, 0, self, bus_id)

        self.mht.delete_bus(bus_id)
        self.mht.commit()

        self.notify_popup_command()

    def show_cpu_settings(self, cpu, x, y):
        wnd = CPUSettingsWindow(self,
            cpu = cpu,
            machine = self.mach,
            machine_history_tracker = self.mht,
        )

        geom = "+" + str(int(self.winfo_rootx() + x)) \
             + "+" + str(int(self.winfo_rooty() + y))

        wnd.geometry(geom)

    def on_popup_single_cpu_settings(self):
        _id = self.current_popup_tag

        x0, y0 = self.canvasx(0), self.canvasy(0)
        x, y = self.coords(_id)[-2:]
        x = x - x0
        y = y - y0

        cpu = self.node2dev[self.id2node[_id]]

        self.show_cpu_settings(cpu, x, y)

        self.notify_popup_command()

    def on_popup_single_cpu_delete(self):
        cpu_id = self.current_popup_tag
        node = self.id2node[cpu_id]
        cpu_id = self.node2dev[node].id

        if node.x != 0 or node.y != 0:
            # move node to 0, 0 to preserve its coordinates
            self.mht.stage(MWOp_MoveNode, 0, 0, self, cpu_id)

        self.mht.delete_cpu(cpu_id)
        self.mht.commit()

        self.notify_popup_command()

    def on_popup_multiple_delete(self):
        self.delete_ids(self.current_popup_tag)
        self.notify_popup_command()

    def delete_selected(self):
        self.delete_ids(list(self.selected))

    def on_key_delete(self, event):
        if self.selected:
            to_del = self.selected

            self.selected = []
            self.event_generate(MachineDiagramWidget.EVENT_SELECT)

            self.delete_ids(to_del)

    def delete_ids(self, ids):
        to_del = []
        for sid in ids:
            try:
                n = self.id2node[sid]
                mach_n = self.node2dev[n]
            except KeyError:
                continue
            else:
                node_id = mach_n.id

                if isinstance(mach_n, (DeviceNode, BusNode, IRQHub, CPUNode)):
                    if n.x != 0 or n.y != 0:
                        # move node to 0, 0 to preserve its coordinates
                        self.mht.stage(MWOp_MoveNode, 0, 0, self, node_id)

                to_del.append(node_id)

        self.mht.delete_ids(to_del)
        self.mht.start_new_sequence()

    def on_add_irq_hub(self):
        x, y = self.popup_x - self.winfo_rootx() + self.canvasx(0), \
               self.popup_y - self.winfo_rooty() + self.canvasy(0)

        # print("Adding IRQ hub: %i, %i" % (x, y))

        node_id = self.mach.get_free_id()

        self.mht.stage(MOp_AddIRQHub, node_id)
        self.mht.stage(MWOp_MoveNode, x, y, self, node_id)
        self.mht.set_sequence_description(_("IRQ hub creation."))
        self.mht.commit()

        self.notify_popup_command()

    def add_bus_at_popup(self, class_name):
        x, y = self.popup_x - self.winfo_rootx() + self.canvasx(0), \
               self.popup_y - self.winfo_rooty() + self.canvasy(0)

        node_id = self.mach.get_free_id()

        self.mht.add_bus(class_name, node_id)
        self.mht.stage(MWOp_MoveNode, x, y, self, node_id)
        self.mht.commit()

        self.notify_popup_command()

    def on_add_bus_common(self):
        self.add_bus_at_popup("BusNode")

    def on_add_bus_system(self):
        self.add_bus_at_popup("SystemBusNode")

    def on_add_bus_pci_e(self):
        self.add_bus_at_popup("PCIExpressBusNode")

    def on_add_bus_isa(self):
        self.add_bus_at_popup("ISABusNode")

    def on_add_bus_ide(self):
        self.add_bus_at_popup("IDEBusNode")

    def on_add_bus_i2c(self):
        self.add_bus_at_popup("I2CBusNode")

    def add_device_at_popup(self, class_name, bus = None):
        x, y = self.popup_x - self.winfo_rootx() + self.canvasx(0), \
               self.popup_y - self.winfo_rooty() + self.canvasy(0)

        node_id = self.mach.get_free_id()

        self.mht.add_device(class_name, node_id)
        self.mht.stage(MWOp_MoveNode, x, y, self, node_id)
        if bus:
            self.mht.stage(MOp_SetDevParentBus, bus, node_id)
        self.mht.commit()

        self.notify_popup_command()

    def on_add_cpu(self):
        x = self.popup_x - self.winfo_rootx() + self.canvasx(0)
        y = self.popup_y - self.winfo_rooty() + self.canvasy(0)

        node_id = self.mach.get_free_id()

        self.mht.add_cpu(node_id)
        self.mht.stage(MWOp_MoveNode, x, y, self, node_id)
        self.mht.commit()

        self.notify_popup_command()

    def on_add_common_device(self):
        self.add_device_at_popup("DeviceNode")

    def get_bus_labels(self, bus_type_name):
        for bl in self.buslabels:
            if type(bl.node).__name__ == bus_type_name:
                yield bl

    def get_bus_label_at_popup(self, bus_type_name):
        x = self.popup_x - self.winfo_rootx() + self.canvasx(0)

        ranged_bls = sorted(self.get_bus_labels(bus_type_name),
            key = lambda n : abs(n.busline.x - x)
        )
        return ranged_bls[0] if ranged_bls else None

    def get_bus_at_popup(self, bus_type_name):
        bl = self.get_bus_label_at_popup(bus_type_name)

        return None if bl is None else bl.node

    def on_add_system_bus_device(self):
        self.add_device_at_popup("SystemBusDeviceNode",
            bus = self.get_bus_at_popup("SystemBusNode")
        )

    def on_add_pci_e_function(self):
        self.add_device_at_popup("PCIExpressDeviceNode",
            bus = self.get_bus_at_popup("PCIExpressBusNode")
        )

    def __switch_show_mesh(self):
        self.var_show_mesh.set(not self.var_show_mesh.get())

    def __check_show_mesh(self, alt):
        show = (alt or self.var_show_mesh.get())

        if self.display_mesh != show:
            self.display_mesh = show

            if show:
                m = self.mesh_step.get()

                self.__create_mesh(
                    -m, -m,
                    self.winfo_width() + m, self.winfo_height() + m
                )
            else:
                self.delete("mesh")

    def __on_show_mesh(self, *args):
        self.__check_show_mesh(self.__alt_is_held())

    def __create_mesh(self, wx1, wy1, wx2, wy2):
        m = self.mesh_step.get()

        x1, y1 = (
            int(self.canvasx(wx1, gridspacing = m)),
            int(self.canvasy(wy1, gridspacing = m))
        )
        x2, y2 = (
            int(self.canvasx(wx2, gridspacing = m)),
            int(self.canvasy(wy2, gridspacing = m))
        )

        # small step requires special handling
        if m >= 15:
            dash = (5, m - 5)
            dashoffset = 2
        elif m >= 6:
            dash = (3, m - 3)
            dashoffset = 1
        else:
            if m == 1:
                m = 5
            elif m == 2:
                m = 4
            dash = (1, m - 1)
            dashoffset = 0

        kw = {
            "dash" : dash,
            "tags" : "mesh",
            "fill" : "blue",
            "dashoffset" : dashoffset
        }

        cl = self.create_line
        for x in xrange(x1, x2 + 1, m):
            cl(x, y1, x, y2, **kw)

        for y in xrange(y1, y2 + 1, m):
            cl(x1, y, x2, y, **kw)

        self.lower("mesh")

    def __on_mesh_step(self, *args):
        self.__repaint_mesh()

    def __repaint_mesh(self):
        # Repaint the mesh
        if self.display_mesh:
            m = self.mesh_step.get()
            self.delete("mesh")
            self.__create_mesh(
                -m, -m,
                self.winfo_width() + m, self.winfo_height() + m
            )

    def __on_resize(self, *args):
        self.__repaint_mesh()

    def __key_is_held(self, code):
        try:
            return self.key_state[code]
        except KeyError:
            return False

    def on_key_press(self, event):
        self.key_state[event.keycode] = True

        alt = self.__alt_is_held()

        self.align = alt

        self.__check_show_mesh(alt)

    def on_key_release(self, event):
        self.key_state[event.keycode] = False

        alt = self.__alt_is_held()

        self.align = alt

        self.__check_show_mesh(alt)

    def __alt_is_held(self):
        return self.__key_is_held(64) or self.__key_is_held(108)

    def __shift_is_held(self):
        return self.__key_is_held(50) or self.__key_is_held(62)

    def on_b1_press(self, event):
        event.widget.focus_set()

        # If user pressed on a draggable item, the state is already set by
        # <ButtonPress-1> handler of super class. Because this event handler
        # is binded after it.
        if self._state is not None:
            return
        self._state = rect_selecting

        x, y = self.canvasx(event.x), self.canvasy(event.y)
        self.select_point = (x, y)

        self.select_frame = self.create_rectangle(
            x, y, x + 1, y + 1,
            fill = "",
            outline = self.select_frame_color
        )

    def get_id_priority(self, _id):
        try:
            n = self.id2node[_id]
            if isinstance(n, IRQPathCircle):
                # IRQ Line circles could discourage another nodes dragging,
                # especially related IRQ hub nodes. Hence, make IRQ line
                # circles less priority.
                ret = 1
                # There is no meaningful reason to distribute other nodes
                # priorities such way. So, just try and watch what will happen.
            elif isinstance(n, IRQLine):
                # The _id corresponds to arrow of a highlighted IRQ line.
                # Sometimes an IRQ path circle is shown for different (not
                # currently highlighted) line.
                ret = 2
            elif isinstance(n, IRQHubCircle):
                ret =  3
            else:
                n = self.node2dev[n]

                if isinstance(n, DeviceNode):
                    ret =  4
                elif isinstance(n, BusNode):
                    ret =  5
                else:
                    # Unspecified node. Make it much intrusive to speed up its
                    # priority specification.
                    ret =  6
        except KeyError:
            # print("item %d without a descriptor has minimal priority" % _id)
            return 0

        # print("%u priority %u (%s)" % (_id, ret, type(n).__name__))

        return ret

    def sort_ids_by_priority(self, ids):
        return sorted(ids, reverse = True, key = lambda _id : (
            self.get_id_priority(_id)
        ))

    def on_b1_release(self, event):
        if self._state is not rect_selecting:
            # select item if it has been touched but not been dragged
            touched = self.touched
            if touched is not None:
                self._select_ids(True, touched)
            return
        self._state = None

        bbox = self.bbox(self.select_frame)
        touched = self.find_enclosed(*bbox)
        touched = self.sort_ids_by_priority(touched)

        self.delete(self.select_frame)
        self.select_frame = None

        self._select_ids(False, *touched)

    def _select_ids(self, exclude_selected, *touched):
        touched_ids = []
        for t in touched:
            if ("DnD" in self.gettags(t)) and (t in self.id2node):
                if t == self.shown_irq_circle:
                    # IRQ line selection is not supported yet.
                    continue
                touched_ids.append(t)

        shift = self.__shift_is_held()

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
                if exclude_selected:
                    if tid in self.selected:
                        self.selected.remove(tid)
                        self.event_generate(MachineDiagramWidget.EVENT_SELECT)
                    else:
                        self.selected.append(tid)
                        self.event_generate(MachineDiagramWidget.EVENT_SELECT)
                elif tid not in self.selected:
                    self.selected.append(tid)
                    self.event_generate(MachineDiagramWidget.EVENT_SELECT)
        elif not self.selected == touched_ids:
            self.selected = list(touched_ids)
            self.event_generate(MachineDiagramWidget.EVENT_SELECT)

        self.invalidate()

    def on_b3_press(self, event):
        event.widget.focus_set()

        if self._state is not None:
            return # User already using mouse for something

        # Shift + right button press => delete IRQ line circle
        self.circle_was_deleted = False
        if self.__shift_is_held():
            self.update_highlighted_irq_line()

            if self.highlighted_irq_line and self.shown_irq_circle:
                self.irq_line_delete_circle(
                    *self.__line_and_node_idx_of_shown_irq_circle()
                )
                self.invalidate()
                self.circle_was_deleted = True
                return

        CanvasDnD.b3down(self, event)

        # print("on_b3_press")

    def dnd_all(self, _):
        self.hide_popup()

    def dnd_all_moved(self, _):
        self.__repaint_mesh()
        # cancel current physic iteration if moved
        self.invalidate()

    def dnd_all_up(self, e):
        self.all_were_dragged = self._state is dragging_all

    def on_b3_release(self, event):
        # print("on_b3_release")
        for n in self.nodes + self.buslabels + self.circles:
            n.static = False

        self.update_highlighted_irq_line()

        if self.all_were_dragged:
            return # we should not show popup

        if self.circle_was_deleted:
            return
        # else: show popup menu

        x, y = self.canvasx(event.x), \
               self.canvasy(event.y)

        if self.highlighted_irq_line:
            if self.shown_irq_circle:
                self.circle_to_be_deleted = \
                    self.__line_and_node_idx_of_shown_irq_circle()
            else:
                self.circle_to_be_deleted = None

            self.popup_irq_line.entryconfig(
                self.on_popup_irq_line_delete_point_idx,
                state = "disabled" if self.circle_to_be_deleted is None \
                    else "normal"
            )

            self.stop_circle_preview()

            if self.circle_to_be_deleted:
                tag = self.circle_to_be_deleted
            else:
                tag = self.highlighted_irq_line

            popup = self.popup_irq_line
        else:
            touched_ids = self.find_overlapping(
                x - 3, y - 3,
                x + 3, y + 3
            )

            if touched_ids:
                touched_ids = self.sort_ids_by_priority(touched_ids)
                popup = None

                for tid in touched_ids:
                    if not "DnD" in self.gettags(tid):
                        continue
                    if not tid in self.id2node:
                        continue

                    shift = self.__shift_is_held()
                    if shift:
                        if not tid in self.selected:
                            self.selected.append(tid)
                            self.event_generate(
                                MachineDiagramWidget.EVENT_SELECT
                            )
                    else:
                        if not tid in self.selected:
                            self.selected = [tid]
                            self.event_generate(
                                MachineDiagramWidget.EVENT_SELECT
                            )

                    # touched node
                    tnode = self.id2node[tid]

                    if not tnode in self.node2dev:
                        continue

                    # touched device, etc..
                    tdev = self.node2dev[tnode]

                    if len(self.selected) == 1:
                        if isinstance(tdev, DeviceNode):
                            popup = self.popup_single_device
                        elif isinstance(tdev, IRQHub):
                            popup = self.popup_single_irq_hub
                        elif isinstance(tdev, BusNode):
                            popup = self.popup_single_bus
                        elif isinstance(tdev, CPUNode):
                            popup = self.popup_single_cpu
                        else:
                            continue
                        tag = tid
                        break
                    else:
                        popup = self.popup_multiple
                        tag = list(self.selected)
                        break
                else:
                    popup = self.popup_empty_no_selected
                    tag = None
            else:
                if self.selected:
                    self.selected = []
                    self.event_generate(MachineDiagramWidget.EVENT_SELECT)

                popup = self.popup_empty_no_selected
                tag = None

        if popup:
            self.show_popup(event.x_root, event.y_root, popup, tag)
        else:
            self.hide_popup()

    def update_highlighted_irq_line(self):
        x, y = self.last_canvas_mouse

        nearest = (None, float_info.max)
        for irql in self.irq_lines:
            for seg_id in irql.lines:
                x0, y0, x1, y1 = tuple(self.coords(seg_id))
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
                self.lift(self.shown_irq_circle)

    def motion_all(self, event):
        # print("motion_all")

        mx, my = event.x, event.y
        x, y = self.canvasx(mx), self.canvasy(my)
        self.last_canvas_mouse = x, y

        if self._state is rect_selecting:
            # TODO: Because canvas reorders points of the rectangle (first
            # point is always to the top & left of second one),
            # we can't distinguish which of point is starting and which is
            # "current" (to be replaced with event's (x, y)).
            # So, we can't eliminate `select_point` now.
            self.coords(*[
                self.select_frame,
                self.select_point[0], self.select_point[1],
                x, y
            ])
            return

        if self.shown_irq_circle:
            if not self.shown_irq_circle in self.find_overlapping(
                x - 3, y - 3, x + 3, y + 3
            ):
                self.hide_irq_line_circle()
        else:
            for c in self.circles:
                if not isinstance(c, IRQPathCircle):
                    continue
                dx, dy = x - (c.x + c.r), y - (c.y + c.r)
                if c.r >= sqrt(dx * dx + dy * dy):
                    self.shown_irq_circle = self.create_oval(
                        c.x, c.y,
                        c.x + c.r * 2, c.y + c.r * 2,
                        fill = "white",
                        tags = "DnD"
                    )
                    self.shown_irq_node = c
                    break

        # If IRQ line popup menu is showed, then do not change IRQ highlighting
        if self.current_popup is not self.popup_irq_line:
            self.update_highlighted_irq_line()

    def dnd_moved(self, event):
        self.touched = None

        _id = self.dnd_dragged
        if _id == self.shown_irq_circle:
            node = self.shown_irq_node
        else:
            node = self.id2node[_id]

        points = self.coords(_id)[:2]
        points[0] = points[0] - node.offset[0]
        points[1] = points[1] - node.offset[1]

        # moving of non-selected item while other are selected
        if self.selected:
            if not _id in self.selected:
                if self.__shift_is_held():
                    self.selected.append(_id)
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

                if isinstance(n, TextBox):
                    self.apply_node(n)
        else:
            node.x = points[0]
            node.y = points[1]

            if isinstance(node, TextBox):
                self.apply_node(node)

        # cancel current physic iteration if moved
        self.invalidate()

    def dnd_down(self, event):
        _id = self.dnd_dragged

        self.touched = _id

        if _id == self.irq_circle_preview:
            self.tmp_irq_circle = (
                self.highlighted_irq_line,
                self.circle_preview_to_irq(self.highlighted_irq_line),
                self.last_canvas_mouse[0], self.last_canvas_mouse[1]
            )
        else:
            self.tmp_irq_circle = None

        if _id == self.shown_irq_circle:
            node = self.shown_irq_node
        else:
            node = self.id2node[_id]

        if _id in self.selected:
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

        tirq = self.tmp_irq_circle
        if tirq is not None:
            # If new IRQ line point was not dragged far enough then remove it.
            if not self.ph_is_running():
                # During dynamic laying out point removal is automated.
                lcm = self.last_canvas_mouse
                dx = abs(tirq[2] - lcm[0])
                dy = abs(tirq[3] - lcm[1])
                # Use Manchester metric to speed up the check
                if dx + dy <= DRAG_GAP:
                    self.irq_line_delete_circle(tirq[0], tirq[1])
                    self.invalidate()
                    self.update_highlighted_irq_line()

            self.tmp_irq_circle = None

    def __update_var_names(self):
        t = self.mach.gen_type()

        # provide names for variables of all nodes
        t.reset_generator()

        ni2vn = self.mach.node_id2var_name

        for n, v in t.node_map.items():
            if isinstance(n, (text_type, binary_type)):
                continue

            nid = n.id
            sv = ni2vn.setdefault(nid, StringVar())
            if sv.get() != v:
                sv.set(v)

    def update(self):
        irqs = list(self.mach.irqs)

        for cpu in self.mach.cpus:
            if cpu in self.dev2node:
                continue
            cpu_node = TextBox(cpu)

            self.dev2node[cpu] = cpu_node
            self.node2dev[cpu_node] = cpu

            self.add_node(cpu_node, None)

        for hub in self.mach.irq_hubs:
            if hub in self.dev2node:
                continue
            hub_node = IRQHubCircle(hub)

            self.dev2node[hub] = hub_node
            self.node2dev[hub_node] = hub

            self.add_irq_hub(hub_node)

        for bus in self.mach.buses:
            if bus in self.dev2node:
                continue

            node = BusLabel(bus)

            self.dev2node[bus] = node
            self.node2dev[node] = bus

            self.add_buslabel(node)

        for dev in self.mach.devices:
            if not dev in self.dev2node:
                node = TextBox(dev)

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
            if not pb in self.dev2node:
                continue
            pbn = self.dev2node[pb].busline

            self.add_conn(node, pbn)

        for irq in irqs:
            if irq in self.dev2node:
                continue

            src = self.dev2node[irq.src_dev]
            dst = self.dev2node[irq.dst_dev]

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

        t0 = time()
        for x in self.current_ph_iteration:
            t1 = time()
            dt = t1 - t0
            t_limit_sec = t_limit_sec - dt
            if t_limit_sec <= 0:
                return 0
            t0 = t1

        self.current_ph_iteration = None
        self.ph_sync()

        t1 = time()
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
                self.delete(self.irq_circle_preview)
                self.irq_circle_preview = None
        else:
            x, y = self.last_canvas_mouse
            coords = [
                x - self.irq_circle_r, y - self.irq_circle_r,
                x + self.irq_circle_r, y + self.irq_circle_r
            ]
            if not self.irq_circle_preview:
                self.irq_circle_preview = self.create_oval(
                    *coords,
                    fill = "white",
                    tags = "DnD"
                )
                self.lift(self.irq_circle_preview)
            else:
                self.coords(self.irq_circle_preview, *coords)

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
            self.delete(self.irq_circle_preview)
            self.irq_circle_preview = None

    def circle_preview_to_irq(self, irql):
        coords = self.coords(self.irq_circle_preview)
        x, y = (coords[0] + coords[2]) / 2, (coords[1] + coords[3]) / 2

        nearest = (0, float_info.max)

        for idx, seg_id in enumerate(irql.lines):
            x0, y0, x1, y1 = tuple(self.coords(seg_id))
            v0 = Vector(x - x0, y - y0)
            v1 = Vector(x - x1, y - y1)
            v2 = Vector(x1 - x0, y1 - y0)
            d = v0.Length() + v1.Length() - v2.Length()

            if d < nearest[1]:
                nearest = (idx, d)

        idx = nearest[0]

        self.shown_irq_node = self.irq_line_add_circle(irql, idx, x, y)
        self.shown_irq_circle = self.irq_circle_preview

        self.irq_circle_preview = None
        self.stop_circle_preview()

        return idx

    def process_irq_circles(self):
        total_circles = 0
        for l in self.irq_lines:
            total_circles += len(l.circles)

        if total_circles > self.irq_circle_total_limit:
            self.irq_circle_per_line_limit = int(self.irq_circle_total_limit /
                len(self.irq_lines))
            if self.irq_circle_per_line_limit == 0:
                self.irq_circle_per_line_limit = 1

            # print("Total circles: %u, CPL: %u" % (total_circles,
            #    self.irq_circle_per_line_limit)
            # )

        for l in self.irq_lines:
            self.ph_process_irq_line(l)

    def update_selection_marks_once(self):
        del self._update_selection_marks_onece

        for idx, sid in enumerate(self.selected):
            bbox = self.bbox(sid)
            self.coords(*[
                self.selection_marks[idx],
                bbox[0] - 1, bbox[1] - 1,
                bbox[2] + 1, bbox[3] + 1
            ])

    def update_selection_marks(self):
        if "_update_selection_marks_onece" in self.__dict__:
            return
        self._update_selection_marks_onece = self.after(1,
            self.update_selection_marks_once
        )

    def ph_sync(self):
        for n in self.nodes:
            if n.bus_labels:
                min_x = n.x + n.width + n.bus_padding
                max_x = n.x - n.bus_padding

                for bl in n.bus_labels:
                    x = bl.x + bl.offset[0] - n.bus_padding
                    if min_x > x:
                        min_x = x

                    x = bl.x + bl.offset[0] + n.bus_padding
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

                self.coords(*([self.shown_irq_circle] + points))

        self.process_irq_circles()

        self.update_selection_marks()

        for n, idtext in list(self.node2idtext.items()):
            dev = self.node2dev[n]
            if isinstance(dev, Node):
                if isinstance(n, NodeCircle):
                    coords = [n.x + n.r, n.y + n.r]
                else:
                    coords = [n.x + n.width + n.spacing,
                              n.y + n.height + n.spacing]
                self.coords(idtext, *coords)

    def on_select(self, event):
        still_selected = set([])
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
                self.selection_marks.append(self.create_rectangle(
                    0,0,0,0,
                    outline = self.selection_mark_color,
                    fill = ""
                ))
        elif marks > selects:
            for _id in self.selection_marks[selects:]:
                self.delete(_id)
            self.selection_marks = self.selection_marks[:selects]

        if not self.var_physical_layout.get():
            self.update_selection_marks()

    def show_node_id(self, node):
        idtext = self.create_text(
            0, 0,
            text = str(node.node.id),
            state = DISABLED,
            font = self.node_font
        )
        self.node2idtext[node] = idtext

    def hide_node_id(self, node):
        idtext = self.node2idtext[node]
        self.delete(idtext)
        del self.node2idtext[node]

    def ph_iter_all_objects(self):
        for n in self.nodes:
            yield n
            c = n.conn
            if c is not None:
                yield c
        for bl in self.buslabels:
            yield bl
            yield bl.busline
        for c in self.circles:
            yield c
        for l in self.irq_lines:
            for c in l.circles:
                yield c
            # TODO: also yield lines between circles

    def ph_iterate_co(self):
        all_nodes = self.nodes + self.buslabels + self.circles
        dynamic = [n for n in all_nodes if not n.static]

        yield

        for n in dynamic:
            n.vx = n.vy = 0

        yield

        nbl = self.nodes + self.buslabels

        for idx, n in enumerate(nbl):
            for n1 in nbl[idx + 1:]:
                if not n.overlaps_box(n1):
                    continue

                w2 = n.width / 2
                h2 = n.height / 2

                w12 = n1.width / 2
                h12 = n1.height / 2

                # distance vector from n center to n1 center
                dx = n1.x + w12 - (n.x + w2)

                while dx == 0:
                    dx = sign(random() - 0.5)

                dy = n1.y + h12 - (n.y + h2) 

                while dy == 0:
                    dy = sign(random() - 0.5)

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
                if not n.touches_vline(b):
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
                    dx = sign(random() - 0.5)

                ix = dx - sign(dx) * (w2 + n.spacing)

                n.vx = n.vx + ix * self.bus_velocity_k

                if parent_device and parent_node:
                    parent_node.vx = parent_node.vx - ix * self.velocity_k

            yield

            for c in self.conns:
                if n.conn == c:
                    continue

                if not n.touches_hline(c):
                    continue

                h2 = n.height / 2
                dy = c.y - (n.y + h2)

                while dy == 0:
                    dy = sign(random() - 0.5)

                iy = dy - sign(dy) * (h2 + n.spacing)

                n.vy = n.vy + iy * self.bus_velocity_k
                c.dev_node.vy = c.dev_node.vy - iy * self.bus_velocity_k

            yield

            for hub in self.circles:
                if not hub.overlaps_box(n):
                    continue

                w2 = n.width / 2
                h2 = n.height / 2

                # distance vector from n center to n1 center
                dx = hub.x + hub.r - (n.x + w2)

                while dx == 0:
                    dx = sign(random() - 0.5)

                dy = hub.y + hub.r - (n.y + h2) 

                while dy == 0:
                    dy = sign(random() - 0.5)

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
                # if (bool(isinstance(h1, IRQPathCircle))
                #  != bool(isinstance(h, IRQPathCircle))
                # ):
                #    continue

                if not h.overlaps_circle(h1):
                    continue

                dx = h1.x + h1.r - (h.x + h.r)

                while dx == 0:
                    dx = sign(random() - 0.5)

                dy = h1.y + h1.r - (h.y + h.r)

                while dy == 0:
                    dy = sign(random() - 0.5)

                scale = float(h.r) / (h.r + h1.r)

                ix = dx * scale
                iy = dy * scale

                ir = sqrt(ix * ix + iy * iy)
                k = (h.r + h.spacing) / ir

                cx = ix * k
                cy = iy * k

                rx = ix - cx
                ry = iy - cy

                if not (
                        isinstance(h, IRQHubCircle)
                    and isinstance(h1, IRQPathCircle)
                ):
                    h.vx = h.vx + rx * self.velocity_k
                    h.vy = h.vy + ry * self.velocity_k
                if not (
                        isinstance(h1, IRQHubCircle)
                    and isinstance(h, IRQPathCircle)
                ):
                    h1.vx = h1.vx - rx * self.velocity_k
                    h1.vy = h1.vy - ry * self.velocity_k

            yield

        for l in self.irq_lines:
            c_len = len(l.circles)
            if not c_len:
                continue

            c = l.circles[0]
            x, y = l.src.get_bind_point((c.x, c.y))
            dx = x - (c.x + c.r)
            dy = y - (c.y + c.r)
            c.vx = c.vx + dx * self.irq_circle_graviry
            c.vy = c.vy + dy * self.irq_circle_graviry

            c = l.circles[-1]
            x, y = l.dst.get_bind_point((c.x, c.y))
            dx = x - (c.x + c.r)
            dy = y - (c.y + c.r)
            c.vx = c.vx + dx * self.irq_circle_graviry
            c.vy = c.vy + dy * self.irq_circle_graviry

            if c_len < 2:
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

        lim = self.velocity_limit

        for n in dynamic:
            vx, vy = n.vx, n.vy

            if abs(vx) > lim:
                vx = sign(vx) * lim
                n.vx = vx
            if abs(vy) > lim:
                vy = sign(vy) * lim
                n.vy = vy

            n.x += vx
            n.y += vy

    def ph_apply_conn(self, c):
        _id = self.node2id[c]
        points = [
            c.x, c.y,
            c.x + c.width, c.y
        ]

        self.coords(_id, *points)

    def ph_apply_buslabel(self, bl):
        _id = self.node2id[bl]
        points = [
            bl.x + bl.width / 2, # x
                bl.y,            # y ...
            bl.x + bl.width,
                bl.y + bl.cap_size * (bl.text_height + bl.padding),
            bl.x + bl.width,
                bl.y + (1 + bl.cap_size) * (bl.text_height + bl.padding),
            bl.x + bl.width / 2,
                bl.y + bl.height,
            bl.x,
                bl.y + (1 + bl.cap_size) * (bl.text_height + bl.padding),
            bl.x,
                bl.y + bl.cap_size * (bl.text_height + bl.padding)
        ]

        self.coords(_id, *points)
        self.apply_node(bl)

    def ph_apply_bus(self, b):
        _id = self.node2id[b]
        points = [
            b.x, b.y,
            b.x, b.y + b.height
        ]

        self.coords(_id, *points)

    def apply_node(self, n):
        p = [n.x + n.width / 2, n.y + n.height / 2]
        self.coords(n.text, *p)

    def ph_apply_node(self, n):
        _id = self.node2id[n]
        points = [
            n.x, n.y,
            n.x + n.width, n.y + n.height
        ]

        self.coords(_id, *points)
        self.apply_node(n)

    def ph_apply_hub(self, h):
        _id = self.node2id[h]
        points = [
            h.x, h.y,
            h.x + 2 * h.r, h.y + 2 * h.r
        ]

        self.coords(_id, *points)

    def irq_line_add_circle(self, l, idx, x, y):
        c = IRQPathCircle(l)
        c.x, c.y = x - self.irq_circle_r, y - self.irq_circle_r
        c.r = self.irq_circle_r

        self.circles.append(c)

        _id = self.create_line(
            0, 0, 1, 1,
            fill = self.irq_line_color
        )
        self.lower(_id)

        l.circles.insert(idx, c)
        l.lines.insert(idx + 1, _id)

        return c

    def irq_line_delete_circle(self, l, idx):
        self.delete(l.lines.pop(idx + 1))
        c = l.circles.pop(idx)

        if c == self.shown_irq_node:
            self.hide_irq_line_circle()

        self.circles.remove(c)

        return c

    def ph_process_irq_line(self, l):
        changed = False
        hand_layout = not self.var_physical_layout.get()

        for i, seg in enumerate(l.lines):
            if i == 0:
                if l.circles:
                    c = l.circles[0]
                    x1, y1 = c.x + c.r, c.y + c.r
                    x0, y0 = l.src.get_bind_point((x1, y1))
                else:
                    x1, y1 = l.dst.get_bind_point(None)
                    x0, y0 = l.src.get_bind_point((x1, y1))
                    x1, y1 = l.dst.get_bind_point((x0, y0))
            elif i == len(l.lines) - 1:
                if l.circles:
                    c = l.circles[i - 1]
                    x0, y0 = c.x + c.r, c.y + c.r
                    x1, y1 = l.dst.get_bind_point((x0, y0))
                else:
                    x0, y0 = l.src.get_bind_point(None)
                    x1, y1 = l.dst.get_bind_point((x0, y0))
                    x0, y0 = l.src.get_bind_point((x1, y1))
            else:
                c = l.circles[i - 1]
                x0, y0 = c.x + c.r, c.y + c.r
                c = l.circles[i]
                x1, y1 = c.x + c.r, c.y + c.r

            # Do not change lines during dragging it could delete currently
            # dragged circle
            # Do not change circles if dynamic layout is turned off.
            line_circles = len(l.circles)

            if not (   self.dragging 
                    or changed 
                    or self.irq_circle_per_line_limit <= line_circles
                    or hand_layout
            ):
                dx = x1 - x0
                dy = y1 - y0
                d = sqrt( dx * dx + dy * dy )

                d1 = (self.irq_circle_r + self.irq_circle_s) * 2

                if d > 2 * d1:
                    x2 = (x0 + x1) / 2
                    y2 = (y0 + y1) / 2

                    self.irq_line_add_circle(l, i, x2, y2)

                    x1 = x2
                    y1 = y2

                    changed = True
                elif (d < 1.5 * d1
                   or line_circles > self.irq_circle_per_line_limit
                ):
                    if i < len(l.lines) - 1:
                        # not last line
                        self.irq_line_delete_circle(l, i)

                        if i < len(l.circles):
                            c = l.circles[i]
                            x1, y1 = c.x + c.r, c.y + c.r
                        else:
                            x1, y1 = l.dst.get_bind_point((x0, y0))

                        changed = True

            self.coords(*([seg] + [x0, y0, x1, y1]))

        # update arrow
        # direction
        dx, dy = x1 - x0, y1 - y0
        # normalize direction
        dl = sqrt(dx * dx + dy * dy)

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
        self.coords(*arrow_coords)

    def ph_launch(self):
        self.var_physical_layout.set(True)

    def __ph_launch__(self):
        if "_ph_run" in self.__dict__:
            raise Exception("Attempt to launch physical simulation twice")

        # If background task manager is available then use coroutine task
        # to compute physics else use legacy "after" based method.
        if self.task_manager is None:
            self._ph_run = self.after(0, self.ph_run)
        else:
            self._ph_run = self.co_ph_task()
            self.task_manager.enqueue(self._ph_run)

    def ph_is_running(self):
        return "_ph_run" in self.__dict__

    def ph_stop(self):
        self.var_physical_layout.set(False)

    def __ph_stop__(self):
        if self.task_manager is None:
            self.after_cancel(self._ph_run)
        else:
            self.task_manager.remove(self._ph_run)
        del self._ph_run

    def ph_run(self):
        rest = self.ph_iterate(0.01)
        if rest < 0.001:
            rest = 0.001

        self._ph_run = self.after(int(rest * 1000), self.ph_run)

    def co_ph_task(self):
        while True:
            rest = self.ph_iterate(0.01)
            # If engine is still computing an iteration
            yield rest <= 0.0

    def update_node_text(self, node):
        text = node.node.qom_type
        if text.startswith("TYPE_"):
            text = text[5:]
        self.itemconfig(node.text, text = text)

        t_bbox = self.bbox(node.text)
        node.text_width = t_bbox[2] - t_bbox[0]
        node.text_height = t_bbox[3] - t_bbox[1]

        node.width = node.text_width + node.padding
        node.height = node.text_height + node.padding

    def place_object(self, obj):
        left, top, right, bottom = find_empty_aabb(self.ph_iter_all_objects(),
            minw = obj.width + 4 * obj.spacing,
            minh = obj.height + 4 * obj.spacing
        )

        if left is None:
            if right is not None:
                obj.x = right - obj.width - 2 * obj.spacing
            # else:
            #     pass # no restriction for node.x, left it as it is
        else:
            obj.x = left + 2 * obj.spacing

        if top is None:
            if bottom is not None:
                obj.y = bottom - obj.height - 2 * obj.spacing
        else:
            obj.y = top + 2 * obj.spacing

    def find_space_near(self, x, y, w, h, spacing):
        objs = list(self.ph_iter_all_objects())
        objs.sort(key = lambda o : (o.x - x) ** 2 + (o.y - y) ** 2)

        left, top, right, bottom = find_empty_aabb(objs,
            minw = w + 2 * spacing,
            minh = h + 2 * spacing
        )

        if left is None:
            if right is not None:
                right -= w + spacing
                if right < x:
                    x = right
            # else:
            #     pass # no restriction for x, left it as it is
        else:
            left += spacing
            if x < left:
                x = left

        if top is None:
            if bottom is not None:
                bottom -= h + spacing
                if bottom < y:
                    y = bottom
        else:
            top += spacing
            if y < top:
                y = top

        return x, y

    def add_node(self, node, buses):
        node.text = self.create_text(
            node.x, node.y,
            state = DISABLED,
            font = self.node_font
        )

        self.update_node_text(node)
        self.place_object(node)

        # TODO: replace rectangle with image
        if buses:
            tags = ("DnD", "fixed_x")
            node.bus_labels = [self.dev2node[bus] for bus in buses]
        else:
            tags = "DnD"

        _id = self.create_rectangle(
            node.x, node.y,
            node.x + node.width,
            node.y + node.height,
            fill = "white",
            tag = tags
        )

        self.id2node[_id] = node

        self.lift(node.text)

        self.nodes.append(node)

    def add_irq_hub(self, hub):
        _id = self.create_oval(
            0, 0, 1, 1,
            fill = "white",
            tag = "DnD"
        )

        self.place_object(hub)

        self.id2node[_id] = hub

        self.circles.append(hub)
        self.ph_apply_hub(hub)

    def add_irq_line(self, line):
        _id = self.create_line(
            0, 0, 1, 1,
            fill = self.irq_line_color
        )

        self.lower(_id)
        line.lines.append(_id)

        _id = self.create_polygon(
            0, 0, 0, 0, 0, 0,
            fill = self.irq_line_color
        )
        line.arrow = _id
        self.lower(_id)

        self.id2node[_id] = line

        self.irq_lines.append(line)

    def highlight(self, line, high = True):
        if high:
            color, layer_func, preview_func = self.irq_line_high_color, \
                self.lift, self.start_circle_preview
        else:
            color, layer_func, preview_func = self.irq_line_color, \
                self.lower, self.stop_circle_preview

        for seg_id in line.lines:
            self.itemconfig(seg_id, fill = color)
            layer_func(seg_id)

        self.itemconfig(line.arrow, fill = color)
        layer_func(line.arrow)

        preview_func()

    def add_bus(self, bus):
        _id = self.create_line(
            0, 0, 0, 0
        )
        self.lower(_id)

        self.id2node[_id] = bus

        self.buses.append(bus)

    def update_buslabel_text(self, bl):
        self.itemconfig(bl.text,
            text = bl.node.gen_child_name_for_bus()
        )

        t_bbox = self.bbox(bl.text)
        bl.text_width = t_bbox[2] - t_bbox[0]
        bl.text_height = t_bbox[3] - t_bbox[1]

        bl.width = bl.text_width + bl.padding
        bl.height = (1 + 2 * bl.cap_size) * (bl.text_height + bl.padding)
        bl.offset = [bl.width / 2, 0]

    def add_buslabel(self, bl):
        node = BusLine(bl)
        self.add_bus(node)
        bl.busline = node

        _id = self.create_text(
            bl.x, bl.y,
            state = DISABLED,
            font = self.node_font
        )
        bl.text = _id

        _id = self.create_polygon(
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            fill = "white",
            outline = "black",
            tag = "DnD"
        )

        self.update_buslabel_text(bl)
        self.place_object(bl)

        self.id2node[_id] = bl

        self.lift(_id)
        self.lift(bl.text)

        self.buslabels.append(bl)

    def add_conn(self, dev, bus):
        conn = ConnectionLine(dev, bus)

        _id = self.create_line(
            conn.x, conn.y,
            conn.x + conn.width, conn.y
        )
        self.lower(_id)

        self.id2node[_id] = conn

        dev.conn = conn

        self.conns.append(conn)

    def gen_layout(self):
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
                (c.x + self.irq_circle_r, c.y + self.irq_circle_r)
                    for c in l.circles
            ]

        layout[-1] = {
            LAYOUT_SHOW_MESH        : self.var_show_mesh.get(),
            LAYOUT_MESH_STEP        : self.mesh_step.get(),
            LAYOUT_DYNAMIC          : self.var_physical_layout.get(),
            LAYOUT_IRQ_LINES_POINTS : irqs
        }

        return layout

    def set_layout(self, l):
        layout_bak = self.gen_layout()
        try:
            for id, desc in l.items():
                if id == -1:
                    try:
                        self.var_show_mesh.set(desc[LAYOUT_SHOW_MESH])
                    except KeyError:
                        pass

                    try:
                        step = desc[LAYOUT_MESH_STEP]
                    except KeyError:
                        pass
                    else:
                        if step < MIN_MESH_STEP:
                            step = MIN_MESH_STEP
                        elif step > MAX_MESH_STEP:
                            step = MAX_MESH_STEP

                        self.mesh_step.set(step)

                    try:
                        self.var_physical_layout.set(desc[LAYOUT_DYNAMIC])
                    except KeyError:
                        pass

                    try:
                        irqs = desc[LAYOUT_IRQ_LINES_POINTS]
                    except KeyError:
                        irqs = {}

                    for irq_id, points in irqs.items():
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
            self.set_layout(layout_bak)
