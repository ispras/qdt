from source import \
 Header, \
 Source, \
 Structure, \
 Type, \
 Function, \
 Initializer, \
 Macro

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

        for barN in xrange(0, self.mem_bar_num):
            self.append_field_t_s("MemoryRegion",
                    self.get_Ith_mem_bar_name(barN))

    def get_Ith_mem_bar_name(self, i):
        if self.mem_bar_num == 1:
            return "mem_bar"
        else:
            return "mem_bar_%u" % i

class PCIEDeviceType(QOMType):
    def __init__(self,
        name,
        directory,
        irq_num = 1,
        mem_bar_num = 1,
        msi_messages_num = 2
    ):
        super(PCIEDeviceType, self).__init__(name)

        self.irq_num = irq_num
        self.mem_bar_num = mem_bar_num
        self.msi_messages_num = msi_messages_num

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

        source_path = "hw/%s/%s.c"% (directory, self.qtn.for_header_name)
        self.source = Source(source_path)

        self.device_realize = Function(
            name = "%s_realize" % self.qtn.for_id_name,
            body = """\
    __attribute__((unused)) {Struct} *s = {UPPER}(dev);
""".format(
        Struct = self.state_struct.name,
        UPPER = self.type_cast_macro.name,
    ),
            args = [
                Type.lookup("PCIDevice").gen_var("dev", pointer = True),
                Type.lookup("Error*").gen_var("errp", pointer = True)],
            static = True,
            used_types = [self.state_struct]
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

    pc->realize = {dev}_realize;
    pc->exit   = {dev}_exit;
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
                Type.lookup("PCIDeviceClass"),
                self.device_realize,
                self.device_exit],
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
