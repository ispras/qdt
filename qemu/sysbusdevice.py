__all__ = [ "SysBusDeviceType" ]

from .qom import \
    QOMDevice, \
    QOMType

from source import \
    Macro, \
    Initializer, \
    Function, \
    Type

from common import \
    mlget as _

from collections import \
    OrderedDict

from .qom_desc import \
    Describable

@Describable
class SysBusDeviceType(QOMDevice):
    __attribute_info__ = OrderedDict([
        ("out_irq_num", { "short": _("Output IRQ quantity"), "input": int }),
        ("in_irq_num", { "short": _("Input IRQ quantity"), "input": int }),
        ("mmio_num", { "short": _("MMIO quantity"), "input": int }),
        ("pio_num", { "short": _("PMIO (PIO) quantity"), "input": int })
    ])

    def __init__(self,
        name,
        directory,
        out_irq_num = 1,
        in_irq_num = 0,
        mmio_num = 1, 
        pio_num = 0,
        **qomd_kw
    ):

        super(SysBusDeviceType, self).__init__(name, directory, **qomd_kw)

        self.out_irq_num = out_irq_num
        self.in_irq_num = in_irq_num
        self.mmio_num = mmio_num
        self.pio_num = pio_num

        self.mmio_size_macros = []
        self.pio_size_macros = []
        self.pio_address_macros = []

        self.add_state_field_h("SysBusDevice", "parent_obj", save = False)

        for irqN in range(0, self.out_irq_num):
            self.add_state_field_h("qemu_irq", self.get_Ith_irq_name(irqN),
                save = False
            )

        for mmioN in range(0, self.mmio_num):
            self.add_state_field_h("MemoryRegion",
                self.get_Ith_mmio_name(mmioN),
                save = False
            )

        for ioN in range(0, self.pio_num):
            self.add_state_field_h("MemoryRegion",
                self.get_Ith_io_name(ioN),
                save = False
            )

        self.timer_declare_fields()
        self.char_declare_fields()
        self.block_declare_fields()

        self.state_struct = self.gen_state()

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

        self.device_reset = Function(
        "%s_reset" % self.qtn.for_id_name,
            body = """\
    __attribute__((unused))@b{Struct}@b*s@b=@s{UPPER}(dev);
""".format(
        Struct = self.state_struct.name,
        UPPER = self.type_cast_macro.name,
        ),
            args = [Type.lookup("DeviceState").gen_var("dev", True)],
            static = True,
            used_types = [self.state_struct]
            )

        self.source.add_type(self.device_reset) 

        self.device_realize = self.gen_realize("DeviceState")
        self.source.add_type(self.device_realize)

        s_is_used = False
        instance_init_code = ''
        instance_init_used_types = set()
        instance_init_used_globals = []

        mmio_def_size = 0x100

        if self.mmio_num > 0:
            instance_init_used_types.update([
                Type.lookup("sysbus_init_mmio"),
                Type.lookup("memory_region_init_io"),
                Type.lookup("Object")
            ])

        for mmioN in range(0, self.mmio_num):
            size_macro = Macro(
                name = self.gen_Ith_mmio_size_macro_name(mmioN),
                text = "0x%X" % mmio_def_size)

            self.header.add_type(size_macro)
            instance_init_used_types.add(size_macro)

            component = self.get_Ith_mmio_id_component(mmioN)

            read_func = QOMType.gen_mmio_read(
                    name = self.qtn.for_id_name + "_" + component + "_read",
                    struct_name = self.state_struct.name, 
                    type_cast_macro = self.type_cast_macro.name
                    ) 

            write_func = QOMType.gen_mmio_write(
                    name = self.qtn.for_id_name + "_" + component + "_write",
                    struct_name = self.state_struct.name, 
                    type_cast_macro = self.type_cast_macro.name
                    )

            self.source.add_types([read_func, write_func])

            ops_init = Initializer(
                used_types = [read_func, write_func],
                code = """{{
    .read@b=@s{read},
    .write@b=@s{write}
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
    memory_region_init_io(@a&s->{mmio},@sobj,@s&{ops},@ss,@sTYPE_{UPPER},\
@s{size});
    sysbus_init_mmio(@aSYS_BUS_DEVICE(obj),@s&s->{mmio});
""".format(
    mmio = self.get_Ith_mmio_name(mmioN),
    ops = self.gen_Ith_mmio_ops_name(mmioN),
    UPPER = self.qtn.for_macros,
    size = size_macro.name
)
            s_is_used = True

        pio_def_size = 0x4
        pio_cur_addres = 0x1000

        if self.pio_num > 0:
            instance_init_used_types.update([
                Type.lookup("sysbus_add_io"),
                Type.lookup("memory_region_init_io"),
                Type.lookup("Object"),
                Type.lookup("sysbus_init_ioports")
            ])

        for pioN in range(0, self.pio_num):
            size_macro = Macro(
                name = self.gen_Ith_pio_size_macro_name(pioN),
                text = "0x%X" % pio_def_size)
            address_macro = Macro(
                name = self.gen_Ith_pio_address_macro_name(pioN),
                text = "0x%X" % pio_cur_addres)
            pio_cur_addres += pio_def_size

            self.header.add_types([size_macro, address_macro])
            instance_init_used_types.update([size_macro, address_macro])

            component = self.get_Ith_pio_id_component(pioN)

            read_func = QOMType.gen_mmio_read(
                    name = self.qtn.for_id_name + "_" + component + "_read",
                    struct_name = self.state_struct.name, 
                    type_cast_macro = self.type_cast_macro.name
                    ) 

            write_func = QOMType.gen_mmio_write(
                    name = self.qtn.for_id_name + "_" + component + "_write",
                    struct_name = self.state_struct.name, 
                    type_cast_macro = self.type_cast_macro.name
                    )

            self.source.add_types([read_func, write_func])

            ops_init = Initializer(
                used_types = [read_func, write_func],
                code = """{{
    .read@b=@s{read},
    .write@b=@s{write}
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
    memory_region_init_io(@a&s->{pio},@sobj,@s&{ops},@ss,@sTYPE_{UPPER},\
@s{size});
    sysbus_add_io(@aSYS_BUS_DEVICE(obj),@s{addr},@s&s->{pio});
    sysbus_init_ioports(@aSYS_BUS_DEVICE(obj),@s{addr},@s{size});
""".format(
    pio = self.get_Ith_io_name(pioN),
    ops = self.gen_Ith_pio_ops_name(pioN),
    UPPER = self.qtn.for_macros,
    size = size_macro.name,
    addr = address_macro.name
)
            s_is_used = True

        if self.out_irq_num > 0:
            instance_init_used_types.update([
                Type.lookup("qemu_irq"),
                Type.lookup("sysbus_init_irq")
            ])

            instance_init_code += "\n"

            for irqN in range(0, self.out_irq_num):
                instance_init_code += """\
    sysbus_init_irq(@aSYS_BUS_DEVICE(obj),@s&s->%s);
""" % self.get_Ith_irq_name(irqN)

        if self.in_irq_num > 0:
            self.irq_handler = Type.lookup("qemu_irq_handler").\
use_as_prototype(
                name = self.qtn.for_id_name + "_irq_handler",
                static = True,
                used_types = [
                    self.state_struct,
                    self.type_cast_macro],
                body =  """\
    __attribute__((unused))@b{Struct}@b*s@b=@s{UPPER}(opaque);
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
    qdev_init_gpio_in(@aDEVICE(obj),@s{handler},@s{irqs});
""".format(
    handler = self.irq_handler.name,
    irqs = in_irq_macro.name
)

            instance_init_used_types.update([
                self.irq_handler,
                in_irq_macro,
                Type.lookup("qdev_init_gpio_in"),
                Type.lookup("DEVICE")
            ])

        self.instance_init = self.gen_instance_init_fn(self.state_struct,
            code = instance_init_code,
            s_is_used = s_is_used,
            used_types = instance_init_used_types,
            used_globals = instance_init_used_globals
        )

        self.source.add_type(self.instance_init)

        self.vmstate = self.gen_vmstate_var(self.state_struct)

        self.source.add_global_variable(self.vmstate)

        self.gen_property_macros(self.header)
        self.properties = self.gen_properties_global(self.state_struct)

        self.source.add_global_variable(self.properties)

        self.class_init = Function(
            name = "%s_class_init" % self.qtn.for_id_name, 
            body = """\
    DeviceClass@b*dc@b=@sDEVICE_CLASS(oc);

    dc->realize@b=@s{dev}_realize;
    dc->reset@b@b@b=@s{dev}_reset;
    dc->vmsd@b@b@b@b=@s&vmstate_{dev};
    dc->props@b@b@b=@s{dev}_properties;
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

        self.type_info = self.gen_type_info_var(self.state_struct,
            self.instance_init, self.class_init,
            parent_tn = "TYPE_SYS_BUS_DEVICE"
        )

        self.source.add_global_variable(self.type_info)

        self.register_types = self.gen_register_types_fn(self.type_info)

        self.source.add_type(self.register_types)

        type_init_var = Type.lookup("type_init").gen_var()
        type_init_usage_init = Initializer(
            code = { "function": self.register_types }
        )
        self.source.add_usage(
            type_init_var.gen_usage(type_init_usage_init)
            )



    def generate_header(self):
        #header = HeaderFile(self.qtn.get_header_name())
        #header.add_chunk(StructureDeclaration(state_struct))

        # TODO: current value of inherit_references is dictated by Qemu coding
        # policy. Hence, version API must be used there.
        header_source = self.header.generate(inherit_references = True)

        return header_source;

    def generate_source(self):
        return self.source.generate()

    def get_Ith_mmio_id_component(self, i):
        return self.get_Ith_mmio_name(i)

    def gen_Ith_mmio_size_macro_name(self, i):
        UPPER = self.get_Ith_mmio_id_component(i).upper()
        return "%s_%s_SIZE" % (self.qtn.for_macros, UPPER)

    def gen_Ith_mmio_ops_name(self, i):
        return self.qtn.for_id_name + "_" \
            + self.get_Ith_mmio_id_component(i) + "_ops"

    def get_Ith_pio_id_component(self, i):
        return self.get_Ith_io_name(i)

    def gen_Ith_pio_ops_name(self, i):
        return self.qtn.for_id_name + "_" \
            + self.get_Ith_pio_id_component(i) + "_ops"

    def gen_Ith_pio_size_macro_name(self, i):
        UPPER = self.get_Ith_pio_id_component(i).upper()
        return "%s_%s_SIZE" % (self.qtn.for_macros, UPPER)

    def gen_Ith_pio_address_macro_name(self, i):
        UPPER = self.get_Ith_pio_id_component(i).upper()
        return "%s_%s_ADDR" % (self.qtn.for_macros, UPPER)

    def get_Ith_irq_name(self, i):
        if self.out_irq_num == 1:
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
