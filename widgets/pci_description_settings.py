from .device_description_settings import \
    DeviceDescriptionSettingsWidget

from qemu import \
    PCIId

from common import \
    mlget as _

class PCIEBusDeviceDescriptionSettingsWidget(DeviceDescriptionSettingsWidget):
    def __init__(self, *args, **kw):
        DeviceDescriptionSettingsWidget.__init__(self,
            [
                ("vendor", _("Vendor"), PCIId),
                ("device", _("Device"), PCIId),
                ("pci_class", _("Class"), PCIId),
                ("irq_num", _("IRQ pin quantity"), int),
                ("mem_bar_num", _("BAR quantity"), int),
                ("msi_messages_num", _("MSI message quantity"), int),
                ("revision", _("Revision"), int),
                ("subsys_vendor", _("Subsystem vendor"), PCIId),
                ("subsys", _("Subsystem"), PCIId)
            ],
            *args, **kw
        )
        self.qsig_watch("qvd_switched", self.__on_qvd_switched__)

    def __on_qvd_switched__(self):
        for f in self.fields:
            if issubclass(f[1], PCIId):
                self.refresh_field(*f)

    def __on_destory__(self, *args, **kw):
        DeviceDescriptionSettingsWidget.__on_destory__(self, *args, **kw)

        self.qsig_unwatch("qvd_switched", self.__on_qvd_switched__)
