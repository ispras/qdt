from device_description_settings import \
    DeviceDescriptionSettingsWidget

from common import \
    mlget as _

class SystemBusDeviceDescriptionSettingsWidget(DeviceDescriptionSettingsWidget):
    def __init__(self, *args, **kw):
        DeviceDescriptionSettingsWidget.__init__(self,
            [
                ("out_irq_num", _("Output IRQ quantity"), long),
                ("in_irq_num", _("Input IRQ quantity"), long),
                ("mmio_num", _("MMIO quantity"), long),
                ("pio_num", _("PMIO (PIO) quantity"), long)
            ],
            *args, **kw
        )
