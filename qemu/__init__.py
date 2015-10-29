from source import \
 SourceFile, \
 SourceChunk, \
 HeaderFile, \
 HeaderInclusion, \
 StructureDeclaration, \
 VariableDeclaration, \
 Header, \
 TypeReference, \
 Structure

class QemuTypeName():
    def __init__(self, name):
        self.name = name
    
    def get_struct_name(self):
        # parse name to generate one satisfies Qemu coding style
        return self.name
    
    def get_header_name(self):
        # parse name to generate one satisfies Qemu coding style
        return self.name

class QOMType():
    def __init__(self, name):
        self.qtn = QemuTypeName(name)

header_hw_sysbus = Header("hw/sysbus.h")

type_struct_MemoryRegion = TypeReference(
    "MemoryRegion",
    # Through another inclusions
    header_hw_sysbus)

type_struct_SysBusDevice = TypeReference(
    "SysBusDevice",
    header_hw_sysbus
    )

type_qemu_irq = TypeReference(
    "qemu_irq",
    # Through another inclusions
    header_hw_sysbus
    )

class SysBusDeviceStateStruct(Structure):
    def __init__(self,
        name,
        irq_num = 1,
        mmio_num = 1,
        io_num = 0,
    ):
        super(SysBusDeviceStateStruct, self).__init__(name)

        self.append_field_t(type_struct_SysBusDevice, "parent_obj")
        
        for irqN in range(0, irq_num):
            self.append_field_t(type_qemu_irq, "out_irq_{}".format(irqN))
        
        for mmioN in range(0, mmio_num):
            self.append_field_t(type_struct_MemoryRegion, 
                "mmio{}".format(mmioN))
        
        for ioN in range(0, io_num):
            self.append_field_t(type_struct_MemoryRegion,
                "port{}".format(ioN))

class SysBusDeviceType(QOMType):
    def __init__(self,
        name,
        out_irq_num = 1,
        mmio_num = 1, 
        io_num = 0):
        
        super(SysBusDeviceType, self).__init__(name)

        self.out_irq_num = out_irq_num
        self.mmio_num = mmio_num
        self.io_num = io_num
    
    def generate_header(self):
        state_struct = SysBusDeviceStateStruct(
            name = "{}State".format(self.qtn.get_struct_name()),
            irq_num = self.out_irq_num,
            mmio_num = self.mmio_num,
            io_num = self.io_num
            )
        
        header = HeaderFile(self.qtn.get_header_name())
        header.add_chunk(StructureDeclaration(state_struct))
        
        return header

