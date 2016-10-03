from settings_window import \
    SettingsWindow, \
    SettingsWidget

from common import \
    ML as _

from qemu import \
    MOp_SetChildBus, \
    MachineNodeOperation

from var_widgets import \
    VarLabel

from Tkinter import \
    StringVar

from ttk import \
    Combobox

from device_settings import \
    DeviceSettingsWidget

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

    def __apply_internal__(self):
        pass

    def refresh(self):
        values = [
            DeviceSettingsWidget.gen_node_link_text(dev) for dev \
                in ( self.mht.mach.devices + [ None ] )
        ]
        self.cb_parent.config(values = values)

        self.var_parent.set(
            DeviceSettingsWidget.gen_node_link_text(self.bus.parent_device)
        )

    def on_changed(self, op, *args, **kw):
        if isinstance(op, MOp_SetChildBus):
            if self.bus.id in [ op.prev_bus_id, op.bus_id ]:
                self.refresh()
            return

        if not isinstance(op, MachineNodeOperation):
            return

        if op.writes_node():
            if not self.bus.id in self.mht.mach.id2node:
                self.destroy()
            else:
                self.refresh()

class BusSettingsWindow(SettingsWindow):
    def __init__(self, bus, *args, **kw):
        SettingsWindow.__init__(self, *args, **kw)

        self.title(_("Bus settings"))

        self.set_sw(BusSettingsWidget(bus, self.mht, self))
        self.sw.grid(row = 0, column = 0, sticky = "NEWS")
