from .qom_desc import \
    DescriptionOf, \
    QOMDescription

from .pcie import *

@DescriptionOf(PCIExpressDeviceType)
class PCIExpressDeviceDescription(QOMDescription):
    pass
