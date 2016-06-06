from project import QOMDescription
from sysbusdevice import SysBusDeviceType
from pcie import PCIEDeviceType

class SysBusDeviceDescription(QOMDescription):
    def __init__(self,
        name,
        directory,
        out_irq_num = 1,
        in_irq_num = 1,
        mmio_num = 1,
        pio_num = 0
    ):

        QOMDescription.__init__(self, name = name, directory = directory)
        self.out_irq_num = out_irq_num
        self.in_irq_num = in_irq_num
        self.mmio_num = mmio_num
        self.pio_num = pio_num

    def gen_type(self):
        return SysBusDeviceType(
            name = self.name,
            directory = self.directory,
            out_irq_num = self.out_irq_num,
            in_irq_num = self.in_irq_num,
            mmio_num = self.mmio_num,
            pio_num = self.pio_num
            )

class PCIExpressDeviceDescription(QOMDescription):
    def __init__(self,
        name,
        directory,
        vendor,
        device,
        pci_class,
        irq_num = 0,
        mem_bar_num = 1,
        msi_messages_num = 2,
        revision = 0,
        subsys = None,
        subsys_vendor = None
    ):

        QOMDescription.__init__(self, name = name, directory = directory)
        self.vendor = vendor
        self.device = device
        self.pci_class = pci_class
        self.irq_num = irq_num
        self.mem_bar_num = mem_bar_num
        self.msi_messages_num = msi_messages_num
        self.revision = revision
        self.subsys = subsys
        self.subsys_vendor = subsys_vendor

    def gen_type(self):
        return PCIEDeviceType(
            name = self.name,
            directory = self.directory,
            vendor = self.vendor,
            device = self.device,
            pci_class = self.pci_class,
            irq_num = self.irq_num,
            mem_bar_num = self.mem_bar_num,
            msi_messages_num = self.msi_messages_num,
            revision = self.revision,
            subsys = self.subsys,
            subsys_vendor = self.subsys_vendor
            )