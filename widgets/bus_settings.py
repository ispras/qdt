from settings_window import \
    SettingsWindow, \
    SettingsWidget

from common import \
    ML as _

class BusSettingsWidget(SettingsWidget):
    def __init__(self, bus, *args, **kw):
        SettingsWidget.__init__(self, *args, **kw)

        self.bus = bus

    def __apply_internal__(self):
        pass

    def refresh(self):
        pass

    def on_changed(self, op, *args, **kw):
        pass

class BusSettingsWindow(SettingsWindow):
    def __init__(self, bus, *args, **kw):
        SettingsWindow.__init__(self, *args, **kw)

        self.title(_("Bus settings"))

        self.sw = BusSettingsWidget(bus, self.mht, self)
        self.sw.grid(row = 0, column = 0, sticky = "NEWS")
