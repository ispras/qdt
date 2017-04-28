from .qom_desc import \
    DescriptionOf, \
    QOMDescription

from .sysbusdevice import \
    SysBusDeviceType

from .pcie import \
    PCIEDeviceType

@DescriptionOf(SysBusDeviceType)
class SysBusDeviceDescription(QOMDescription):
    pass

@DescriptionOf(PCIEDeviceType)
class PCIExpressDeviceDescription(QOMDescription):
    pass
