from source import \
 Header, \
 Source, \
 Structure, \
 Type, \
 Function, \
 Initializer, \
 Macro \
 , TypeNotRegistered

from qemu import \
 QOMType

class PCIEDeviceStateStruct(Structure):
    def __init__(self,
        name,
        irq_num,
        mem_bar_num,
        msi_messages_num,
    ):
        super(PCIEDeviceStateStruct, self).__init__(name)

        self.irq_num = irq_num
        self.mem_bar_num = mem_bar_num
        self.msi_messages_num = msi_messages_num

        self.append_field_t_s("PCIDevice", "parent_obj")

        for irqN in range(0, irq_num):
            self.append_field_t_s("qemu_irq", 
                self.get_Ith_irq_name(irqN))

        for barN in xrange(0, self.mem_bar_num):
            self.append_field_t_s("MemoryRegion",
                    self.get_Ith_mem_bar_name(barN))

    def get_Ith_mem_bar_name(self, i):
        if self.mem_bar_num == 1:
            return "mem_bar"
        else:
            return "mem_bar_%u" % i

    def get_Ith_irq_name(self, i):
        if self.irq_num == 1:
            return "irq"
        else:
            return "irq_{}".format(i)

class PCIEDeviceType(QOMType):
    def __init__(self,
        name,
        directory,
        vendor,
        device,
        pci_class,
        irq_num = 0,
        mem_bar_num = 1,
        msi_messages_num = 2,
        revision = 1
    ):
        super(PCIEDeviceType, self).__init__(name)

        self.irq_num = irq_num
        self.mem_bar_num = mem_bar_num
        self.msi_messages_num = msi_messages_num
        
        self.revision = revision

        self.vendor = vendor
        self.device = device
        self.pci_class = pci_class

        self.mem_bar_size_macros = []

        """
        There is too many code same as in SysBusDeviceType constructor...
        """
        
        self.struct_name = "%sState" % self.qtn.for_struct_name

        header_path = "hw/%s/%s.h" % (directory, self.qtn.for_header_name)
        try:
            self.header = Header.lookup(header_path)
        except Exception:
            self.header = Header(header_path)

        self.state_struct = PCIEDeviceStateStruct(
            name = self.struct_name,
            irq_num = self.irq_num,
            mem_bar_num = self.mem_bar_num,
            msi_messages_num = self.msi_messages_num
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

        self.vendor_macro = self.vendor.find_macro()
        try:
            self.device_macro = self.device.find_macro()
        except TypeNotRegistered:
            # TODO: add device id macro to pci_ids.h
            self.header.add_type(Macro(
                    name = "PCI_DEVICE_ID_%s_%s" % (self.vendor.name,
                            self.device.name), 
                    text = self.device.id))

            self.device_macro = self.device.find_macro()

        self.pci_class_macro = self.pci_class.find_macro()

        source_path = "hw/%s/%s.c"% (directory, self.qtn.for_header_name)
        self.source = Source(source_path)

        realize_code = ''
        realize_used_types = []
        realize_used_globals = []

        mem_bar_def_size = 0x100

        if self.mem_bar_num > 0:
            realize_used_types.extend([
                Type.lookup("sysbus_init_mmio"),
                Type.lookup("memory_region_init_io"),
                Type.lookup("Object")
                ]
            )

        for barN in range(0, self.mem_bar_num):
            size_macro = Macro(
                name = self.gen_Ith_mem_bar_size_macro_name(barN),
                text = "0x%X" % mem_bar_def_size)
        
            self.header.add_type(size_macro)
            realize_used_types.append(size_macro)
            
            component = self.get_Ith_mem_bar_id_component(barN)
            
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
                name = self.gen_Ith_mem_bar_ops_name(barN),
                pointer = False,
                initializer = ops_init,
                static = True
            )

            self.source.add_global_variable(ops)
            realize_used_globals.append(ops)

            realize_code += """
    memory_region_init_io(&s->{bar}, OBJECT(dev), &{ops}, s, TYPE_{UPPER}, {size});
    pci_register_bar(&s->parent_obj, {barN}, PCI_BASE_ADDRESS_SPACE_MEMORY, &s->{bar});
""".format(
    barN = barN,
    bar = self.state_struct.get_Ith_mem_bar_name(barN),
    ops = self.gen_Ith_mem_bar_ops_name(barN),
    UPPER = self.qtn.for_macros,
    size = size_macro.name
)

        realize_used_types.append(self.state_struct)

        self.device_realize = Function(
            name = "%s_realize" % self.qtn.for_id_name,
            body = """\
    {unused}{Struct} *s = {UPPER}(dev);
{extra_code}\
""".format(
        unused = "__attribute__((unused)) " if realize_code == '' else "",
        Struct = self.state_struct.name,
        UPPER = self.type_cast_macro.name,
        extra_code = realize_code
    ),
            args = [
                Type.lookup("PCIDevice").gen_var("dev", pointer = True),
                Type.lookup("Error*").gen_var("errp", pointer = True)],
            static = True,
            used_types = realize_used_types,
            used_globals = realize_used_globals
            )
        self.source.add_type(self.device_realize)

        self.device_exit = Function(
            name = "%s_exit" % self.qtn.for_id_name,
            args = [Type.lookup("PCIDevice").gen_var("dev", pointer = True)],
            static = True,
            used_types = [self.state_struct],
            body = """\
    __attribute__((unused)) {Struct} *s = {UPPER}(dev);
""".format(
        Struct = self.state_struct.name,
        UPPER = self.type_cast_macro.name,
    )
        )
        self.source.add_type(self.device_exit)

        vmstate_init = Initializer(
            """{{
    .name = TYPE_{UPPER},
    .version_id = 1,
    .fields = (VMStateField[]) {{
        VMSTATE_PCI_DEVICE(parent_obj, {Struct}),
        VMSTATE_END_OF_LIST()
    }}
}}""".format(
    UPPER = self.qtn.for_macros,
    Struct = self.state_struct.name
    ), 
            used_types = [
                Type.lookup("VMStateField"),
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
    PCIDeviceClass *pc = PCI_DEVICE_CLASS(oc);

    pc->realize   = {dev}_realize;
    pc->exit      = {dev}_exit;
    pc->vendor_id = {vendor_macro};
    pc->device_id = {device_macro};
    pc->class_id  = {pci_class_macro};
    pc->revision  = {revision};
    dc->vmsd      = &vmstate_{dev};
    dc->props     = {dev}_properties;
""".format(dev = self.qtn.for_id_name,
           revision = self.revision,
           vendor_macro = self.vendor_macro.name,
           device_macro = self.device_macro.name,
           pci_class_macro = self.pci_class_macro.name
           ),
            args = [
Type.lookup("ObjectClass").gen_var("oc", True),
Type.lookup("void").gen_var("opaque", True),
            ],
            static = True,
            used_types = [
                Type.lookup("DeviceClass"),
                Type.lookup("PCIDeviceClass"),
                self.device_realize,
                self.device_exit,
                self.vendor_macro,
                self.device_macro,
                self.pci_class_macro],
            used_globals = [
                    self.vmstate,
                    self.properties
                ]
            )
        self.source.add_type(self.class_init)

        type_info_init = Initializer(
            code = """{{
    .name          = TYPE_{UPPER},
    .parent        = TYPE_PCI_DEVICE,
    .instance_size = sizeof({Struct}),
    .class_init    = {class_init}
}}""".format(
    UPPER = self.qtn.for_macros,
    Struct = self.state_struct.name,
    class_init = self.class_init.name
),
            used_types = [
                self.state_struct,
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
        return self.header.generate()
    
    def generate_source(self):
        return self.source.generate()

    def get_Ith_mem_bar_id_component(self, i):
        return self.state_struct.get_Ith_mem_bar_name(i)

    def gen_Ith_mem_bar_size_macro_name(self, i):
        UPPER = self.get_Ith_mem_bar_id_component(i).upper()
        return "%s_%s_SIZE" % (self.qtn.for_macros, UPPER)

    def gen_Ith_mem_bar_ops_name(self, i):
        return self.qtn.for_id_name + "_" \
            + self.get_Ith_mem_bar_id_component(i) + "_ops"
