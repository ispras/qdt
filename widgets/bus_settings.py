__all__ = [
    "BusSettingsWindow"
  , "BusSettingsWidget"
]

from common import (
    mlget as _,
)
from .device_settings import (
    DeviceSettingsWidget,
)
from .gui_frame import (
    GUIFrame,
)
from .hotkey import (
    HKEntry,
)
from qemu import (
    BusNode,
    MachineNodeOperation,
    MOp_SetBusAttr,
    MOp_SetChildBus,
)
from .settings_window import (
    SettingsWidget,
    SettingsWindow,
)
from .var_widgets import (
    VarCheckbutton,
    VarLabel,
)

from six.moves.tkinter import (
    BooleanVar,
    BOTH,
    StringVar,
)
from six.moves.tkinter_ttk import (
    Combobox,
)


# `object` is for `property`
class BusSettingsWidget(SettingsWidget, object):

    def __init__(self, *args, **kw):
        kw["node"] = bus = kw.pop("bus")
        SettingsWidget.__init__(self, *args, **kw)

        self.bus_fr = fr = GUIFrame(self)
        fr.pack(fill = BOTH, expand = False)

        fr.columnconfigure(0, weight = 0)
        fr.columnconfigure(1, weight = 1)
        fr.rowconfigure(0, weight = 0)

        l = VarLabel(fr, text = _("Parent device"))
        l.grid(row = 0, column = 0, sticky = "NES")

        self.var_parent = StringVar()
        self.cb_parent = Combobox(fr,
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
                l = VarLabel(fr, text = text)
                v = StringVar()
                w = HKEntry(fr, textvariable = v)
            elif _type is bool:
                l = None
                v = BooleanVar()
                w = VarCheckbutton(fr, text = text, variable = v)

            fr.rowconfigure(row, weight = 0)
            if l is None:
                w.grid(row = row, column = 0, sticky = "NEWS",
                    columnspan = 2
                )
            else:
                l.grid(row = row, column = 0, sticky = "NES")
                w.grid(row = row, column = 1, sticky = "NEWS")

            setattr(self, "w_" + field, w)
            setattr(self, "var_" + field, v)

    @property
    def bus(self):
        return self.node

    def __apply_internal__(self):
        bus = self.node
        new_parent = self.find_node_by_link_text(self.var_parent.get())
        cur_parent = bus.parent_device

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
                    self.mht.disconnect_child_bus(bus.id)
            else:
                self.mht.append_child_bus(new_parent_id, bus.id)

        for (__, field, _type) in self.fields:
            new_val = getattr(self, "var_" + field).get()
            cur_val = getattr(bus, field)

            if new_val == cur_val:
                continue

            self.mht.stage(MOp_SetBusAttr, field, new_val, bus.id)

        self.mht.set_sequence_description(
            _("Bus %d configuration.") % bus.id
        )

    def refresh(self):
        SettingsWidget.refresh(self)

        bus = self.node

        values = [
            DeviceSettingsWidget.gen_node_link_text(dev) for dev \
                in ( self.mach.devices + [ None ] )
        ]
        self.cb_parent.config(values = values)

        self.var_parent.set(
            DeviceSettingsWidget.gen_node_link_text(bus.parent_device)
        )

        for (__, field, _type) in self.fields:
            var = getattr(self, "var_" + field)
            cur_val = getattr(bus, field)

            var.set(cur_val)

    def on_changed(self, op, *__, **___):
        bus = self.node
        if isinstance(op, MOp_SetChildBus):
            if bus.id in [ op.prev_bus_id, op.bus_id ]:
                self.refresh()
            return

        if not isinstance(op, MachineNodeOperation):
            return

        if op.writes_node():
            if bus.id not in self.mach.id2node:
                self.destroy()
            else:
                self.refresh()


class BusSettingsWindow(SettingsWindow):

    def __init__(self, *args, **kw):
        kw["node"] = bus = kw.pop("bus")
        SettingsWindow.__init__(self, *args, **kw)

        self.title(_("Bus settings"))

        self.set_sw(BusSettingsWidget(self,
            bus = bus,
            machine = self.mach,
        ))
        self.sw.grid(row = 0, column = 0, sticky = "NEWS")
