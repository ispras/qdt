from settings_window import \
    SettingsWindow, \
    SettingsWidget

from common import \
    ML as _

from qemu import \
    MachineNodeOperation

class BusSettingsWidget(SettingsWidget):
    def __init__(self, bus, *args, **kw):
        SettingsWidget.__init__(self, *args, **kw)

        self.bus = bus

    def __apply_internal__(self):
        pass

    def refresh(self):
        pass

    def on_changed(self, op, *args, **kw):
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
