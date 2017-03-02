from .settings_window import \
    SettingsWindow, \
    SettingsWidget

from common import \
    mlget as _

from qemu import \
    MOp_SetChildBus, \
    MachineNodeOperation

from .var_widgets import \
    VarCheckbutton, \
    VarLabel

from six.moves.tkinter import \
    BooleanVar, \
    StringVar

from six.moves.tkinter_ttk import \
    Combobox

from .device_settings import \
    DeviceSettingsWidget

from qemu import \
    MOp_SetBusAttr, \
    BusNode

from .hotkey import \
    HKEntry

class BusSettingsWidget(SettingsWidget):
    def __init__(self, bus, *args, **kw):
        SettingsWidget.__init__(self, *args, **kw)

        self.bus = bus

        self.columnconfigure(0, weight = 0)
        self.columnconfigure(1, weight = 1)
        self.rowconfigure(0, weight = 0)

        l = VarLabel(self, text = _("Parent device"))
        l.grid(row = 0, column = 0, sticky = "NES")

        self.var_parent = StringVar()
        self.cb_parent = Combobox(self,
            textvariable = self.var_parent,
            state = "readonly"
        )
        self.cb_parent.grid(row = 0, column = 1, sticky = "NEWS")

        self.fields = []
        if type(bus) is BusNode:
            self.fields.extend([
                (_("C type"), "c_type", str),
                (_("Casting macro"), "cast", str),
                (_("Child name"), "child_name", str),
                (_("Always show index"), "force_index", bool)
            ])

        # Common bus type
        for row, (text, field, _type) in enumerate(self.fields, start = 1):
            if _type is str:
                l = VarLabel(self, text = text)
                v = StringVar()
                w = HKEntry(self, textvariable = v)
            elif _type is bool:
                l = None
                v = BooleanVar()
                w = VarCheckbutton(self, text = text, variable = v)

            self.rowconfigure(row, weight = 0)
            if l is None:
                w.grid(row = row, column = 0, sticky = "NEWS",
                    columnspan = 2
                )
            else:
                l.grid(row = row, column = 0, sticky = "NES")
                w.grid(row = row, column = 1, sticky = "NEWS")

            setattr(self, "w_" + field, w)
            setattr(self, "var_" + field, v)

    def __apply_internal__(self):
        new_parent = self.find_node_by_link_text(self.var_parent.get())
        cur_parent = self.bus.parent_device

        if new_parent is None:
            new_parent_id = -1
        else:
            new_parent_id = new_parent.id

        if cur_parent is None:
            cur_parent_id = -1
        else:
            cur_parent_id = cur_parent.id

        if not new_parent_id == cur_parent_id:
            if new_parent_id == -1:
                if not cur_parent_id == -1:
                    self.mht.disconnect_child_bus(self.bus.id)
            else:
                self.mht.append_child_bus(new_parent_id, self.bus.id)

        prev_pos = self.mht.pos

        for (text, field, _type) in self.fields:
            new_val = getattr(self, "var_" + field).get()
            cur_val = getattr(self.bus, field)

            if new_val == cur_val:
                continue

            self.mht.stage(MOp_SetBusAttr, field, new_val, self.bus.id)

        if prev_pos is not self.mht.pos:
            self.mht.set_sequence_description(
                _("Bus %d configuration.") % self.bus.id
            )

    def refresh(self):
        values = [
            DeviceSettingsWidget.gen_node_link_text(dev) for dev \
                in ( self.mach.devices + [ None ] )
        ]
        self.cb_parent.config(values = values)

        self.var_parent.set(
            DeviceSettingsWidget.gen_node_link_text(self.bus.parent_device)
        )

        for (text, field, _type) in self.fields:
            var = getattr(self, "var_" + field)
            cur_val = getattr(self.bus, field)

            var.set(cur_val)

    def on_changed(self, op, *args, **kw):
        if isinstance(op, MOp_SetChildBus):
            if self.bus.id in [ op.prev_bus_id, op.bus_id ]:
                self.refresh()
            return

        if not isinstance(op, MachineNodeOperation):
            return

        if op.writes_node():
            if not self.bus.id in self.mach.id2node:
                self.destroy()
            else:
                self.refresh()

class BusSettingsWindow(SettingsWindow):
    def __init__(self, bus, *args, **kw):
        SettingsWindow.__init__(self, *args, **kw)

        self.title(_("Bus settings"))

        self.set_sw(BusSettingsWidget(bus, self.mach, self))
        self.sw.grid(row = 0, column = 0, sticky = "NEWS")
