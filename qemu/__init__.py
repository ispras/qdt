from source import \
 Header, \
 Source, \
 Structure, \
 Type, \
 Function, \
 Initializer, \
 Macro

import os

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

    def gen_register_types_name(self):
        return "%s_register_types" % self.qtn.for_id_name
    
    def gen_type_info_name(self):
        return "%s_info" % self.qtn.for_id_name

def initialize(include_path):
    header_db_fname = "header_db.json"
    if os.path.isfile(header_db_fname):
        print("Loading Qemu header inclusion tree from " + header_db_fname)
        Header.load_header_db(header_db_fname)
    else:
        print("Building Qemu header inclusion tree")
        Header.build_inclusions(include_path)

    print("Saving Qemu header inclusion tree to " + header_db_fname)
    Header.save_header_db(header_db_fname)

    Header.lookup("exec/hwaddr.h").add_types([
        Type("hwaddr", False)
        ])
    
    Header.lookup("qom/object.h").add_types([
        Type("ObjectClass", False),
        Type("Object", False),
        Type("TypeInfo", False),
        Type("Type", False),
        Function(name = "type_register_static",
            ret_type = Type.lookup("Type"),
            args = [
                Type.lookup("TypeInfo").gen_var("info", pointer = True)
            ]
        )
        ])
    
    Header.lookup("exec/memory.h").add_types([
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
            [   Type.lookup("MemoryRegionOps_read").gen_var("read"),
                Type.lookup("MemoryRegionOps_write").gen_var("write"),
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
    
    Header.lookup("exec/ioport.h").add_types([
        Type("pio_addr_t", incomplete=False)
        ])
    
    Header.lookup("hw/sysbus.h").add_types([
        Type("SysBusDevice", False),
        Type("qemu_irq", False),
        Function(name = "sysbus_init_mmio",
            ret_type = Type.lookup("void"),
            args = [
                Type.lookup("SysBusDevice").gen_var("dev", pointer = True),
                Type.lookup("MemoryRegion").gen_var("memory", pointer = True)
            ]
        ),
        Function(name = "sysbus_init_irq",
            ret_type = Type.lookup("void"),
            args = [
                Type.lookup("SysBusDevice").gen_var("dev", pointer = True),
                Type.lookup("qemu_irq").gen_var("p", pointer = True)
            ]
        ),
        Function(name = "sysbus_add_io",
            ret_type = Type.lookup("void"),
            args = [
                Type.lookup("SysBusDevice").gen_var("dev", pointer = True),
                Type.lookup("hwaddr").gen_var("addr"),
                Type.lookup("MemoryRegion").gen_var("mem", pointer = True)
            ]
        ),
        Function(name = "sysbus_init_ioports",
            ret_type = Type.lookup("void"),
            args = [
                Type.lookup("SysBusDevice").gen_var("dev", pointer = True),
                Type.lookup("pio_addr_t").gen_var("dev"),
                Type.lookup("pio_addr_t").gen_var("dev")
            ]
        )
        ])
    
    Header.lookup("hw/irq.h").add_types([
        Function(name = "qemu_irq_handler",
            ret_type = Type.lookup("void"),
            args = [
                Type.lookup("void").gen_var("opaque", pointer = True),
                Type.lookup("int").gen_var("n"),
                Type.lookup("int").gen_var("level")
            ]
        )
    ])
    
    Header.lookup("hw/qdev-core.h").add_types([
        Type("DeviceClass", False),
        Type("DeviceState", False),
        Macro(name = "DEVICE", args = ["obj"]),
        Type("Property", False),
        Function(name = "qdev_init_gpio_in",
            ret_type = Type.lookup("void"),
            args = [
                Type.lookup("DeviceState").gen_var("dev", pointer = True),
                Type.lookup("qemu_irq_handler").gen_var("handler"),
                Type.lookup("int").gen_var("n")
            ]
        )
        ])
    
    Header.lookup("qapi/error.h").add_types([
        Type("Error*", False)
        ])
    
    Header.lookup("migration/vmstate.h").add_types([
        Type("VMStateDescription", False),
        Type("VMStateField", False)
        ])
    
    Header.lookup("qemu/module.h").add_types([
        Macro(name = "type_init", 
            args = [
                "function"
            ]
        )
        ])

    Header.lookup("hw/pci/pci.h").add_types([
        Type("PCIDevice", False),
        Type("PCIDeviceClass", False)
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
        directory,
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

        self.mmio_size_macros = []
        self.pio_size_macros = []
        self.pio_address_macros = []

        # Define header file
        header_path = "hw/%s/%s.h" % (directory, self.qtn.for_header_name)
        try:
            self.header = Header.lookup(header_path)
        except Exception:
            self.header = Header(header_path)

        self.state_struct = SysBusDeviceStateStruct(
            name = self.struct_name,
            irq_num = self.out_irq_num,
            mmio_num = self.mmio_num,
            pio_num = self.pio_num
            )

        self.header.add_type(self.state_struct)

        self.type_name_macros = Macro(
            name = "TYPE_%s" % self.qtn.for_macros,
            text = '"%s"' % self.qtn.for_id_name
            )

        self.header.add_type(self.type_name_macros)

        self.type_cast_macro = Macro(
            name = self.qtn.for_macros, 
            args = ["obj"],
            text = "OBJECT_CHECK({Struct}, (obj), TYPE_{UPPER})".format(
    UPPER = self.qtn.for_macros,
    Struct = self.struct_name
)
            )

        self.header.add_type(self.type_cast_macro)

        # Define source file
        self.source = Source("hw/%s/%s.c"% (directory, 
            self.qtn.for_header_name))
        
        self.device_reset = Function(
        "%s_reset" % self.qtn.for_id_name,
            body = """\
    __attribute__((unused)) {Struct} *s = {UPPER}(dev);
""".format(
        Struct = self.state_struct.name,
        UPPER = self.type_cast_macro.name,
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
        UPPER = self.type_cast_macro.name,
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
        instance_init_used_globals = []
        
        mmio_def_size = 0x100

        if self.mmio_num > 0:
            instance_init_used_types.extend([
                Type.lookup("sysbus_init_mmio"),
                Type.lookup("memory_region_init_io"),
                Type.lookup("Object")
                ]
            )

        for mmioN in range(0, self.mmio_num):
            size_macro = Macro(
                name = self.gen_Ith_mmio_size_macro_name(mmioN),
                text = "0x%X" % mmio_def_size)
        
            self.header.add_type(size_macro)
            instance_init_used_types.append(size_macro)
            
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
            instance_init_used_globals.append(ops)

            instance_init_code += """
    memory_region_init_io(&s->{mmio}, obj, &{ops}, s, TYPE_{UPPER}, {size});
    sysbus_init_mmio(SYS_BUS_DEVICE(obj), &s->{mmio});
""".format(
    mmio = self.state_struct.get_Ith_mmio_name(mmioN),
    ops = self.gen_Ith_mmio_ops_name(mmioN),
    UPPER = self.qtn.for_macros,
    size = size_macro.name
)
        pio_def_size = 0x4
        pio_cur_addres = 0x1000

        if self.pio_num > 0:
            instance_init_used_types.extend([
                Type.lookup("sysbus_add_io"),
                Type.lookup("memory_region_init_io"),
                Type.lookup("Object"),
                Type.lookup("sysbus_init_ioports")
                ]
            )

        for pioN in range(0, self.pio_num):
            size_macro = Macro(
                name = self.gen_Ith_pio_size_macro_name(pioN),
                text = "0x%X" % pio_def_size)
            address_macro = Macro(
                name = self.gen_Ith_pio_address_macro_name(pioN),
                text = "0x%X" % pio_cur_addres)
            pio_cur_addres += pio_def_size
            
            self.header.add_types([size_macro, address_macro])
            instance_init_used_types.extend([size_macro, address_macro])
            
            component = self.get_Ith_pio_id_component(pioN)
            
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
                name = self.gen_Ith_pio_ops_name(pioN),
                pointer = False,
                initializer = ops_init,
                static = True
            )

            self.source.add_global_variable(ops)
            instance_init_used_globals.append(ops)

            instance_init_code += """
    memory_region_init_io(&s->{pio}, obj, &{ops}, s, TYPE_{UPPER}, {size});
    sysbus_add_io(SYS_BUS_DEVICE(obj), {addr}, &s->{pio});
    sysbus_init_ioports(SYS_BUS_DEVICE(obj), {addr}, {size});
""".format(
    pio = self.state_struct.get_Ith_io_name(pioN),
    ops = self.gen_Ith_pio_ops_name(pioN),
    UPPER = self.qtn.for_macros,
    size = size_macro.name,
    addr = address_macro.name
)

        if self.out_irq_num > 0:
            instance_init_used_types.extend([
                Type.lookup("qemu_irq"),
                Type.lookup("sysbus_init_irq")
                ])

            instance_init_code += "\n"

            for irqN in range(0, self.out_irq_num):
                instance_init_code += """\
    sysbus_init_irq(SYS_BUS_DEVICE(obj), &s->%s);
""" % self.state_struct.get_Ith_irq_name(irqN)

        if self.in_irq_num > 0:
            self.irq_handler = Type.lookup("qemu_irq_handler").\
use_as_prototype(
                name = self.qtn.for_id_name + "_irq_handler",
                static = True,
                used_types = [
                    self.state_struct,
                    self.type_cast_macro],
                body =  """\
    __attribute__((unused)) {Struct} *s = {UPPER}(opaque);
""".format(
        Struct = self.state_struct.name,
        UPPER = self.type_cast_macro.name,
        )   )

            self.source.add_type(self.irq_handler)

            in_irq_macro = Macro(
                name = "%s_IN_IRQ_NUM" % self.qtn.for_macros,
                text = "%d" % self.in_irq_num
                )

            self.header.add_type(in_irq_macro)

            instance_init_code += """
    qdev_init_gpio_in(DEVICE(obj), {handler}, {irqs});
""".format(
    handler = self.irq_handler.name,
    irqs = in_irq_macro.name
)

            instance_init_used_types.extend([
                self.irq_handler,
                in_irq_macro,
                Type.lookup("qdev_init_gpio_in"),
                Type.lookup("DEVICE")
                ])


        instance_init_used_types.extend([
            self.state_struct,
            self.type_cast_macro
            ])
        self.instance_init = Function(
            name = self.gen_instance_init_name(),
            body = """\
    {Struct} *s = {UPPER}(obj);
{extra_code}\
""".format(
    Struct = self.state_struct.name,
    UPPER = self.qtn.for_macros,
    extra_code = instance_init_code
),
            static = True,
            args = [
                Type.lookup("Object").gen_var("obj", pointer = True)
            ],
            used_types = instance_init_used_types,
            used_globals = instance_init_used_globals
        )
        
        self.source.add_type(self.instance_init)

        vmstate_init = Initializer(
            """{{
    .name = TYPE_{UPPER},
    .version_id = 1,
    .fields = (VMStateField[]) {{
        VMSTATE_END_OF_LIST()
    }}
}}""".format(UPPER = self.qtn.for_macros), 
            used_types = [
                Type.lookup("VMStateField"),
                # It actually will be used when fields will be declared
                self.state_struct
            ])

        self.vmstate = Type.lookup("VMStateDescription").gen_var(
            name = "vmstate_%s" % self.qtn.for_id_name,
            static = True,
            initializer = vmstate_init
            )

        self.source.add_global_variable(self.vmstate)

        properties_init = Initializer(
"""{
    DEFINE_PROP_END_OF_LIST()
}"""
            )

        self.properties = Type.lookup("Property").gen_var(
            name = "%s_properties[]" % self.qtn.for_id_name,
            static = True,
            initializer = properties_init
            )

        self.source.add_global_variable(self.properties)

        self.class_init = Function(
            name = "%s_class_init" % self.qtn.for_id_name, 
            body = """\
    DeviceClass *dc = DEVICE_CLASS(oc);

    dc->realize = {dev}_realize;
    dc->reset   = {dev}_reset;
    dc->vmsd    = &vmstate_{dev};
    dc->props   = {dev}_properties;
""".format(dev = self.qtn.for_id_name),
            args = [
Type.lookup("ObjectClass").gen_var("oc", True),
Type.lookup("void").gen_var("opaque", True),
            ],
            static = True,
            used_types = [
                Type.lookup("DeviceClass"),
                self.device_realize,
                self.device_reset],
            used_globals = [
                    self.vmstate,
                    self.properties
                ]
            )
 
        self.source.add_type(self.class_init)

        type_info_init = Initializer(
            code = """{{
    .name          = TYPE_{UPPER},
    .parent        = TYPE_SYS_BUS_DEVICE,
    .instance_size = sizeof({Struct}),
    .instance_init = {instance_init},
    .class_init    = {class_init}
}}""".format(
    UPPER = self.qtn.for_macros,
    Struct = self.state_struct.name,
    instance_init = self.instance_init.name,
    class_init = self.class_init.name
),
            used_types = [
                self.state_struct,
                self.instance_init,
                self.class_init
            ]
            )
        
        self.type_info = Type.lookup("TypeInfo").gen_var(
            name = self.gen_type_info_name(),
            static = True,
            initializer = type_info_init
            )
        
        self.source.add_global_variable(self.type_info)
        
        self.register_types = Function(
            name = self.gen_register_types_name(),
            body = """\
    type_register_static(&{type_info});
""".format(
    type_info = self.gen_type_info_name()
), 
            static = True, 
            used_types = [
                Type.lookup("type_register_static")
            ],
            used_globals = [self.type_info])
        
        self.source.add_type(self.register_types)

        type_init_var = Type.lookup("type_init").gen_var()
        type_init_usage_init = Initializer(
            code = {
                "function": self.register_types.name },
            used_types = [
                self.register_types]
            )
        self.source.add_usage(
            type_init_var.gen_usage(type_init_usage_init)
            )
        

    
    def generate_header(self):
        #header = HeaderFile(self.qtn.get_header_name())
        #header.add_chunk(StructureDeclaration(state_struct))
        
        header_source = self.header.generate()
        
        return header_source;

    def generate_source(self):
        return self.source.generate()

    def get_Ith_mmio_id_component(self, i):
        return self.state_struct.get_Ith_mmio_name(i)

    def gen_Ith_mmio_size_macro_name(self, i):
        UPPER = self.get_Ith_mmio_id_component(i).upper()
        return "%s_%s_SIZE" % (self.qtn.for_macros, UPPER)

    def gen_Ith_mmio_ops_name(self, i):
        return self.qtn.for_id_name + "_" \
            + self.get_Ith_mmio_id_component(i) + "_ops"

    def get_Ith_pio_id_component(self, i):
        return self.state_struct.get_Ith_io_name(i)

    def gen_Ith_pio_ops_name(self, i):
        return self.qtn.for_id_name + "_" \
            + self.get_Ith_pio_id_component(i) + "_ops"

    def gen_Ith_pio_size_macro_name(self, i):
        UPPER = self.get_Ith_pio_id_component(i).upper()
        return "%s_%s_SIZE" % (self.qtn.for_macros, UPPER)

    def gen_Ith_pio_address_macro_name(self, i):
        UPPER = self.get_Ith_pio_id_component(i).upper()
        return "%s_%s_ADDR" % (self.qtn.for_macros, UPPER)

    def gen_instance_init_name(self):
        return "%s_instance_init" % self.qtn.for_id_name

