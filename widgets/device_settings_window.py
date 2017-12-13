from widgets import (
    SystemBusDeviceSettingsWidget,
    DeviceSettingsWidget
)
from common import mlget as _

import qemu

from .pci_device_settings import PCIDeviceSettingsWidget

from .settings_window import SettingsWindow

class DeviceSettingsWindow(SettingsWindow):
    def __init__(self, *args, **kw):
        device = kw.pop("device")

        SettingsWindow.__init__(self, device, *args, **kw)

        self.title(_("Device settings"))

        self.grid()
        self.columnconfigure(0, weight = 1)

        self.rowconfigure(0, weight = 1)

        if isinstance(device, qemu.SystemBusDeviceNode):
            dsw_class = SystemBusDeviceSettingsWidget
        elif isinstance(device, qemu.PCIExpressDeviceNode):
            dsw_class = PCIDeviceSettingsWidget
        else:
            dsw_class = DeviceSettingsWidget

        self.set_sw(dsw_class(device, self.mach, self))
        self.sw.grid(row = 0, column = 0, sticky = "NEWS")
