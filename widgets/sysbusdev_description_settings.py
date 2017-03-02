from .device_description_settings import \
    DeviceDescriptionSettingsWidget

from common import \
    mlget as _

class SystemBusDeviceDescriptionSettingsWidget(DeviceDescriptionSettingsWidget):
    def __init__(self, *args, **kw):
        DeviceDescriptionSettingsWidget.__init__(self,
            [
                ("out_irq_num", _("Output IRQ quantity"), int),
                ("in_irq_num", _("Input IRQ quantity"), int),
                ("mmio_num", _("MMIO quantity"), int),
                ("pio_num", _("PMIO (PIO) quantity"), int)
            ],
            *args, **kw
        )
