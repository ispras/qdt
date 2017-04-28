from .qom_desc import \
    DescriptionOf, \
    QOMDescription

from .sysbusdevice import *

from .pcie import *

@DescriptionOf(SysBusDeviceType)
class SysBusDeviceDescription(QOMDescription):
    pass

@DescriptionOf(PCIEDeviceType)
class PCIExpressDeviceDescription(QOMDescription):
    pass
