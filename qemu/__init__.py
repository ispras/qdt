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
 Initializer

from _codecs import lookup
from friends.utils.logging import initialize

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

Header("exec/hwaddr.h").add_types([
    Type("hwaddr", False)
    ])

Header("qom/object.h").add_types([
    Type("ObjectClass", False),
    Type("Object", False)
    ])

Header("exec/memory.h").add_types([
    Type("MemoryRegion", False),
    Function(name = "MemoryRegionOps_read",
        ret_type = Type.lookup("uint64_t"),
        args = [
            Type.lookup("void").gen_var("opqaue", pointer = True),
            Type.lookup("hwaddr").gen_var("addr"),
            Type.lookup("unsigned").gen_var("size")
        ]
    ),
    Function(name = "MemoryRegionOps_write",
        ret_type = Type.lookup("void"),
        args = [
            Type.lookup("void").gen_var("opqaue", pointer = True),
            Type.lookup("hwaddr").gen_var("addr"),
            Type.lookup("uint64_t").gen_var("data"),
            Type.lookup("unsigned").gen_var("size")
        ]
    ),
    Structure("MemoryRegionOps", 
        [   Type.lookup("MemoryRegionOps_read").gen_var("read",
                pointer = True),
            Type.lookup("MemoryRegionOps_write").gen_var("write",
                pointer = True),
         ]
    ),
    Function(name = "memory_region_init_io",
        args = [
            Type.lookup("MemoryRegion").gen_var("mr", pointer = True),
            # struct
            Type.lookup("Object").gen_var("owner", pointer = True),
            # const
            Type.lookup("MemoryRegionOps").gen_var("ops", pointer = True),
            Type.lookup("void").gen_var("opaque", pointer = True),
            Type.lookup("const char").gen_var("name", pointer = True),
            Type.lookup("uint64_t").gen_var("size")
        ]
    )
    ])

Header("hw/sysbus.h").add_types([
    Type("SysBusDevice", False),
    Type("qemu_irq", False),
    Function(name = "sysbus_init_mmio",
        ret_type = Type.lookup("void"),
        args = [
            Type.lookup("SysBusDevice").gen_var("dev", pointer = True),
            Type.lookup("MemoryRegion").gen_var("memory", pointer = True)
        ]
    )
    ])

Header("hw/qdev-code.h").add_types([
    Type("DeviceClass", False),
    Type("DeviceState", False)
    ])

Header("qapi/error.h").add_types([
    Type("Error*", False)
    ])

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

        self.append_field_t(Type.lookup("SysBusDevice"), "parent_obj")
        
        for irqN in range(0, irq_num):
            self.append_field_t(Type.lookup("qemu_irq"), 
                self.get_Ith_irq_name(irqN))
        
        for mmioN in range(0, mmio_num):
            self.append_field_t(Type.lookup("MemoryRegion"), 
                self.get_Ith_mmio_name(mmioN))
        
        for ioN in range(0, pio_num):
            self.append_field_t(Type.lookup("MemoryRegion"),
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
            args = [Type.lookup("DeviceState").gen_var("dev", True)],
            static = True,
            used_types = [self.state_struct]
            )
        
        self.source.add_type(self.device_reset) 
        
        self.device_realize = Function(
            name = "%s_realize" % self.qtn.for_id_name,
            body = """\
    __attribute__((unused)) {Struct} *s = {UPPER}(dev);
""".format(
        Struct = self.state_struct.name,
        UPPER = self.qtn.for_macros,
        ),
            args = [
                Type.lookup("DeviceState").gen_var("dev", True),
                Type.lookup("Error*").gen_var("errp", True)
                ],
            static = True,
            used_types = [self.state_struct]
            )
        self.source.add_type(self.device_realize)

        instance_init_code = ''
        instance_init_used_types = []

        if self.mmio_num > 0:
            instance_init_used_types.extend([
                Type.lookup("sysbus_init_mmio"),
                Type.lookup("memory_region_init_io"),
                Type.lookup("Object")
                ]
            )

        for mmioN in range(0, self.mmio_num):
            component = self.get_Ith_mmio_id_component(mmioN)
            
            read_func = Type.lookup("MemoryRegionOps_read").use_as_prototype(
                name = self.qtn.for_id_name + "_" + component + "_read",
                body = "    return 0;\n",
                static = True
            )
            
            write_func = Type.lookup("MemoryRegionOps_write").use_as_prototype(
                name = self.qtn.for_id_name + "_" + component + "_write",
                static = True
            )
            
            self.source.add_types([read_func, write_func])
            
            ops_init = Initializer(
                used_types = [read_func, write_func],
                code = """{{
    .read = {read},
    .write = {write}
}}""".format (
    read = read_func.name,
    write = write_func.name
)
            )

            ops = Type.lookup("MemoryRegionOps").gen_var(
                name = self.gen_Ith_mmio_ops_name(mmioN),
                pointer = False,
                initializer = ops_init,
                static = True
            )
            
            self.source.add_global_variable(ops)
            
            instance_init_code += """
    memory_region_init_io(&s->{mmio}, obj, &{ops}, TYPE_{UPPER}, 0x1000);
    sysbus_init_mmio(SYS_BUS_DEVICE(obj), &s->{mmio});
""".format(
    mmio = self.state_struct.get_Ith_mmio_name(mmioN),
    ops = self.gen_Ith_mmio_ops_name(mmioN),
    UPPER = self.qtn.for_macros
)
        instance_init_used_types.append(self.state_struct)
        self.instance_init = Function(
            name = self.gen_instance_init_name(),
            body = """\
    {Struct} *s = {UPPER}(obj);
    {extra_code}
""".format(
    Struct = self.state_struct.name,
    UPPER = self.qtn.for_macros,
    extra_code = instance_init_code
),
            static = True,
            args = [
                Type.lookup("Object").gen_var("obj", pointer = True)
            ],
            used_types = instance_init_used_types
        )
        
        self.source.add_type(self.instance_init)

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
Type.lookup("ObjectClass").gen_var("oc", True),
Type.lookup("void").gen_var("opaque", True),
            ],
            static = True,
            used_types = [
                Type.lookup("DeviceClass"),
                self.device_realize,
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
    
    def get_Ith_mmio_id_component(self, i):
        return self.state_struct.get_Ith_mmio_name(i)

    def gen_Ith_mmio_ops_name(self, i):
        return self.qtn.for_id_name + "_" \
            + self.get_Ith_mmio_id_component(i) + "_ops"
    
    def gen_instance_init_name(self):
        return "%s_instance_init" % self.qtn.for_id_name