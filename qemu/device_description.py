from .qom_desc import \
    DescriptionOf, \
    QOMDescription

from .pcie import *

@DescriptionOf(PCIEDeviceType)
class PCIExpressDeviceDescription(QOMDescription):
    pass
