__all__ = [
    "IRQHubSettingsWidget",
    "IRQHubSettingsWindow",
]

from .settings_window import \
    SettingsWidget, \
    SettingsWindow

from common import \
    mlget as _

class IRQHubSettingsWidget(SettingsWidget):
    # only common node parameters, no special widgets

    # required by superclass
    def __apply_internal__(self):
        pass

    def on_changed(self, op):
        pass

class IRQHubSettingsWindow(SettingsWindow):
    def __init__(self, *args, **kw):
        SettingsWindow.__init__(self, *args, **kw)

        self.title(_("IRQ hub settings"))

        self.set_sw(IRQHubSettingsWidget(self.node, self.mach, self))
        self.sw.grid(row = 0, column = 0, sticky = "NEWS")
