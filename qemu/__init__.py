from source import \
 SourceFile, \
 SourceChunk, \
 HeaderFile, \
 HeaderInclusion, \
 StructureDeclaration, \
 VariableDeclaration, \
 Header, \
 Source, \
 TypeReference, \
 Structure, \
 Type, \
 Function, \
 Variable, \
 type_void, \
 type_int

class QemuTypeName():
    def __init__(self, name):
        self.name = name.strip()
        
        lower_name = self.name.lower();
        tmp = '_'.join(lower_name.split())
        tmp = '_'.join(tmp.split('-'))
        
        self.for_id_name = tmp
        self.for_header_name = tmp
        
        self.for_struct_name = ''.join(self.name.split())
        
        upper_name = self.name.upper()
        tmp = '_'.join(upper_name.split())
        tmp = '_'.join(tmp.split('-'))
        
        self.for_macros = tmp
    

class QOMType():
    def __init__(self, name):
        self.qtn = QemuTypeName(name)

header_hw_sysbus = Header("hw/sysbus.h")

type_struct_MemoryRegion = Type("MemoryRegion", False)
type_struct_SysBusDevice = Type("SysBusDevice", False)
type_qemu_irq = Type("qemu_irq", False)

header_hw_sysbus.add_type(type_struct_MemoryRegion)
header_hw_sysbus.add_type(type_struct_SysBusDevice)
header_hw_sysbus.add_type(type_qemu_irq)

header_qom_object = Header("qom/object.h")

type_struct_ObjectClass = Type("ObjectClass", False)

header_qom_object.add_type(type_struct_ObjectClass)

header_hw_qdev_core = Header("hw/qdev-code.h")

type_struct_DeviceClass = Type("DeviceClass", False)
type_struct_DeviceState = Type("DeviceState", False)

header_hw_qdev_core.add_type(type_struct_DeviceClass)
header_hw_qdev_core.add_type(type_struct_DeviceState)

class SysBusDeviceStateStruct(Structure):
    def __init__(self,
        name,
        irq_num = 1,
        mmio_num = 1,
        pio_num = 0,
    ):
        super(SysBusDeviceStateStruct, self).__init__(name)
        self.irq_num = irq_num
        self.mmio_num = mmio_num
        self.pio_num = pio_num

        self.append_field_t(type_struct_SysBusDevice, "parent_obj")
        
        for irqN in range(0, irq_num):
            self.append_field_t(type_qemu_irq, self.get_Ith_irq_name(irqN))
        
        for mmioN in range(0, mmio_num):
            self.append_field_t(type_struct_MemoryRegion, 
                self.get_Ith_mmio_name(mmioN))
        
        for ioN in range(0, pio_num):
            self.append_field_t(type_struct_MemoryRegion,
                self.get_Ith_io_name(ioN))
    
    def get_Ith_irq_name(self, i):
        if self.irq_num == 1:
            return "out_irq"
        else:
            return "out_irq_{}".format(i)

    def get_Ith_mmio_name(self, i):
        if self.mmio_num == 1:
            return "mmio"
        else:
            return "mmio_{}".format(i)
            
    def get_Ith_io_name(self, i):
        if self.pio_num == 1:
            return "pio"
        else:
            return "pio_{}".format(i)

class SysBusDeviceType(QOMType):
    def __init__(self,
        name,
        out_irq_num = 1,
        in_irq_num = 0,
        mmio_num = 1, 
        pio_num = 0):
        
        super(SysBusDeviceType, self).__init__(name)

        self.out_irq_num = out_irq_num
        self.in_irq_num = in_irq_num
        self.mmio_num = mmio_num
        self.pio_num = pio_num
        self.struct_name = "{}State".format(self.qtn.for_struct_name)
        
        # Define header file
        self.header = Header("hw/{}.h".format(self.qtn.for_header_name))
        
        self.state_struct = SysBusDeviceStateStruct(
            name = self.struct_name,
            irq_num = self.out_irq_num,
            mmio_num = self.mmio_num,
            pio_num = self.pio_num
            )
        
        self.type_macros = SourceChunk(
            name = "Type cast macros for {}".format(self.qtn.name),
            code = """\
#define TYPE_{UPPER} "{lower}"
#define {UPPER}(obj) OBJECT_CHECK({Struct}, (obj), TYPE_{UPPER})
""".format(
    UPPER = self.qtn.for_macros,
    lower = self.qtn.for_id_name,
    Struct = self.struct_name
        )
            )
        
        self.header.add_type(self.state_struct)
        
        # Define source file
        self.source = Source("hw/%s.c" % self.qtn.for_header_name)
        
        self.device_reset = Function(
        "%s_reset" % self.qtn.for_id_name,
            body = """\
    __attribute__((unused)) {Struct} *s = {UPPER}(dev);
""".format(
        Struct = self.state_struct.name,
        UPPER = self.qtn.for_macros,
        ),
            args = [type_struct_DeviceState.gen_var("dev", True)],
            static = True,
            used_types = [self.state_struct]
            )
        
        self.source.add_type(self.device_reset) 
        
        self.class_init = Function(
            name = "%s_class_init" % self.qtn.for_id_name, 
            body = """\
    DeviceClass *dc = DEVICE_CLASS(oc);
    
    dc->realize = {dev}_realize;
    dc->reset   = {dev}_reset;
    dc->vmsd    = &vmstate_{dev};
    dc->props   = {dev}_props;
""".format(dev = self.qtn.for_id_name),
            args = [
type_struct_ObjectClass.gen_var("oc", True),
type_void.gen_var("opaque", True),
            ],
            static = True,
            used_types = [
                type_struct_DeviceClass,
                self.device_reset]
            )
 
        self.source.add_type(self.class_init)

    
    def generate_header(self):
        #header = HeaderFile(self.qtn.get_header_name())
        #header.add_chunk(StructureDeclaration(state_struct))
        
        header_source = self.header.generate()
        header_source.add_chunk(self.type_macros)
        
        return header_source;

    def generate_source(self):
        return self.source.generate()
