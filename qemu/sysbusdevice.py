__all__ = [
    "SysBusDeviceType"
]

from .qom import (
    QemuTypeName,
    QOMDevice,
    QOMType
)
from source import (
    line_origins,
    Pointer,
    Macro,
    MacroType,
    Initializer,
    Function,
    Type
)
from common import (
    ee,
    mlget as _
)
from collections import (
    OrderedDict
)
from .qom_desc import (
    describable
)
from copy import (
    deepcopy as dcp
)
from .machine_nodes import (
    MemoryLeafNode,
    MemoryRAMNode,
    MemoryROMNode
)
from itertools import (
    count
)


MACROS_2_HEADER = ee("QDT_SBD_MMIO_MACROS_TO_HEADER")


@describable
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
        out_irq_num = 0,
        in_irq_num = 0,
        mmio_num = 0,
        pio_num = 0,
        mmio = None,
        pio = None,
        **qomd_kw
    ):

        super(SysBusDeviceType, self).__init__(name, directory, **qomd_kw)

        self.out_irq_num = out_irq_num
        self.in_irq_num = in_irq_num
        self.mmio_num = mmio_num
        self.pio_num = pio_num

        self.mmio_size_macros = []
        # Qemu requires that any RAM, ROM or ROM device has unique name. Some
        # devices has such MMIOs. Also, different names simplify understanding
        # of `info mtree` HMP command output during debugging.
        self.mmio_name_macros = []
        self.pio_size_macros = []
        self.pio_address_macros = []

        self.mmio = {} if mmio is None else dcp(mmio)
        self.pio = {} if pio is None else dcp(pio)

        self.mmio_names = {}

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
            self.add_fields_for_mmio(self.mmio.get(mmioN, list()))

        for ioN in range(0, self.pio_num):
            self.add_state_field_h("MemoryRegion",
                self.get_Ith_io_name(ioN),
                save = False
            )
            self.add_fields_for_regs(self.pio.get(ioN, list()))

        self.timer_declare_fields()
        self.char_declare_fields()
        self.block_declare_fields()

    def add_fields_for_mmio(self, desc):
        if isinstance(desc, list):
            self.add_fields_for_regs(desc)
        elif isinstance(desc, MemoryLeafNode):
            return # No extra fields
        else:
            raise ValueError("Unsupported MMIO description %s" % desc)

    def fill_header(self):
        self.state_struct = self.gen_state()

        self.header.add_type(self.state_struct)

        self.type_name_macros = Macro(
            name = self.qtn.type_macro,
            text = '"%s"' % self.qtn.for_id_name
        )

        self.header.add_type(self.type_name_macros)

        self.type_cast_macro = Macro(
            name = self.qtn.for_macros,
            args = [ "obj" ],
            text = "OBJECT_CHECK({Struct}, (obj), {TYPE_MACRO})".format(
                TYPE_MACRO = self.qtn.type_macro,
                Struct = self.struct_name
            )
        )

        self.header.add_type(self.type_cast_macro)

        line_origins([
            self.type_name_macros,
            self.type_cast_macro,
            self.state_struct
        ])

        for mmioN in range(0, self.mmio_num):
            size_macro = Macro(
                name = self.gen_Ith_mmio_size_macro_name(mmioN),
                text = self.gen_mmio_size(self.mmio.get(mmioN, None))
            )
            name_macro = Macro(
                name = self.get_Ith_mmio_name_macro_name(mmioN),
                text = '%s "_%s"' % (
                    self.qtn.type_macro,
                    self.get_Ith_mmio_id_component(mmioN)
                )
            )

            (self.header if MACROS_2_HEADER else self.source).add_types([
                size_macro,
                name_macro
            ])

            self.mmio_size_macros.append(size_macro)
            self.mmio_name_macros.append(name_macro)

        pio_def_size = 0x4
        pio_cur_addres = 0x1000

        for pioN in range(0, self.pio_num):
            size_macro = Macro(
                name = self.gen_Ith_pio_size_macro_name(pioN),
                text = "0x%X" % pio_def_size
            )
            address_macro = Macro(
                name = self.gen_Ith_pio_address_macro_name(pioN),
                text = "0x%X" % pio_cur_addres
            )
            pio_cur_addres += pio_def_size

            self.header.add_types([size_macro, address_macro])

            self.pio_size_macros.append(size_macro)
            self.pio_address_macros.append(address_macro)

        if self.in_irq_num > 0:
            self.in_irq_macro = Macro(
                name = self.qtn.for_macros + "_IN_IRQ_NUM",
                text = "%d" % self.in_irq_num
            )

            self.header.add_type(self.in_irq_macro)

        self.gen_property_macros(self.header)

    def fill_source(self):
        s_is_used = False

        all_regs = []
        for idx, regs in self.mmio.items():
            if idx >= self.mmio_num:
                continue
            if isinstance(regs, MemoryLeafNode):
                continue
            all_regs.extend(regs)
        for idx, regs in self.pio.items():
            if idx >= self.pio_num:
                continue
            all_regs.extend(regs)

        reg_resets = []

        used_types = set([self.state_struct])

        for reg in all_regs:
            name = reg.name
            if name is None or name == "gap":
                continue
            qtn = QemuTypeName(name)

            if reg.reset is not None:
                reg_resets.append("s->%s@b=@s%s;" % (
                    qtn.for_id_name,
                    reg.reset.gen_c_code()
                ))
                s_is_used = True

            warb = reg.warbits
            if warb.v:
                # forbid writing to WAR bits just after reset
                wm = reg.wmask
                if wm.v == (1 << (8 * reg.size)) - 1:
                    if reg.size < 4:
                        # Avoid gcc "overflow" warning: large integer
                        # implicitly truncated to unsigned type
                        cast_type = "uint%u_t" % (8 * reg.size)
                        used_types.add(Type[cast_type])
                        cast = "(%s)" % cast_type
                    else:
                        cast = ""

                    reg_resets.append("s->%s_war@b=@s%s~%s;" % (
                        qtn.for_id_name,
                        cast,
                        warb.gen_c_code()
                    ))
                    s_is_used = True
                elif wm.v:
                    reg_resets.append("s->%s_war@b=@s%s@s&@b~%s;" % (
                        qtn.for_id_name,
                        wm.gen_c_code(),
                        warb.gen_c_code()
                    ))
                    s_is_used = True

        self.device_reset = Function(
            name = "%s_reset" % self.qtn.for_id_name,
            body = """\
    {unused}{Struct}@b*s@b=@s{UPPER}(dev);{reset}
""".format(
    unused = "" if s_is_used else "__attribute__((unused))@b",
    Struct = self.state_struct.name,
    UPPER = self.type_cast_macro.name,
    reset = "\n\n    " + "\n    ".join(reg_resets) if reg_resets else ""
            ),
            args = [ Pointer(Type["DeviceState"])("dev") ],
            static = True,
            used_types = used_types
        )

        self.source.add_type(self.device_reset)

        self.device_realize = self.gen_realize("DeviceState")
        self.source.add_type(self.device_realize)

        s_is_used = False
        instance_init_code = ''
        instance_init_used_types = set()
        instance_init_used_globals = []

        if self.mmio_num > 0:
            instance_init_used_types.update([
                Type["sysbus_init_mmio"],
                Type["Object"]
            ])

        for mmioN in range(0, self.mmio_num):
            size_macro = self.mmio_size_macros[mmioN]
            name_macro = self.mmio_name_macros[mmioN]
            instance_init_used_types.update([size_macro, name_macro])

            component = self.get_Ith_mmio_id_component(mmioN)

            regs = self.mmio.get(mmioN, None)

            ops_types = set()

            if isinstance(regs, MemoryROMNode):
                write_func = QOMType.gen_mmio_write(
                    name = self.qtn.for_id_name + "_" + component + "_write",
                    struct_name = self.state_struct.name,
                    type_cast_macro = self.type_cast_macro.name
                )

                ops_types.add(write_func)

                self.source.add_type(write_func)

                read = ""

            elif isinstance(regs, MemoryRAMNode):
                pass
            else:
                read_func = QOMType.gen_mmio_read(
                    name = self.qtn.for_id_name + "_" + component + "_read",
                    struct_name = self.state_struct.name,
                    type_cast_macro = self.type_cast_macro.name,
                    regs = regs
                )

                read = "\n    .read@b=@s" + read_func.name + ","

                write_func = QOMType.gen_mmio_write(
                    name = self.qtn.for_id_name + "_" + component + "_write",
                    struct_name = self.state_struct.name,
                    type_cast_macro = self.type_cast_macro.name,
                    regs = regs
                )

                write_func.extra_references = {read_func}

                ops_types.add(read_func)
                ops_types.add(write_func)

                self.source.add_types([read_func, write_func])

            if isinstance(regs, MemoryRAMNode):
                instance_init_code += """
    memory_region_init_ram(@a&s->{mmio},@sobj,@s{NAME_MACRO},@s{size},@sNULL);
""".format(
    mmio = self.get_Ith_mmio_name(mmioN),
    ops = self.gen_Ith_mmio_ops_name(mmioN),
    NAME_MACRO = name_macro.name,
    size = size_macro.name
                )
                instance_init_used_types.add(Type["memory_region_init_ram"])
            else:
                impl = ""

                if isinstance(regs, list):
                    reg_sizes = set(reg.size for reg in regs)

                    size = regs[0].size # note that all sizes are equal

                    if len(reg_sizes) == 1 and size < 8: # 8 is max size by impl.
                        impl = """,
    .impl = {{
        .max_access_size = {size}
    }}""".format(size = size)

                ops_init = Initializer(
                    used_types = ops_types,
                    code = """{{{read}
    .write@b=@s{write}{impl}
}}""".format(
        read = read,
        write = write_func.name,
        impl = impl
                    )
                )

                ops = Type["MemoryRegionOps"](
                    name = self.gen_Ith_mmio_ops_name(mmioN),
                    pointer = False,
                    initializer = ops_init,
                    static = True,
                    const = True
                )

                self.source.add_global_variable(ops)
                instance_init_used_globals.append(ops)

                if isinstance(regs, MemoryROMNode):
                    instance_init_code += """
    memory_region_init_rom_device(@a&s->{mmio},@sobj,@s&{ops},@ss,\
@s{NAME_MACRO},@s{size},@sNULL);""".format(
    mmio = self.get_Ith_mmio_name(mmioN),
    ops = self.gen_Ith_mmio_ops_name(mmioN),
    NAME_MACRO = name_macro.name,
    size = size_macro.name
                    )
                    instance_init_used_types.add(
                        Type["memory_region_init_rom_device"]
                    )
                else:
                    instance_init_code += """
    memory_region_init_io(@a&s->{mmio},@sobj,@s&{ops},@ss,@s{NAME_MACRO},\
@s{size});""".format(
    mmio = self.get_Ith_mmio_name(mmioN),
    ops = self.gen_Ith_mmio_ops_name(mmioN),
    NAME_MACRO = name_macro.name,
    size = size_macro.name
                    )
                    instance_init_used_types.add(Type["memory_region_init_io"])

            instance_init_code += """
    sysbus_init_mmio(@aSYS_BUS_DEVICE(obj),@s&s->{mmio});
""".format(
    mmio = self.get_Ith_mmio_name(mmioN)
            )

            s_is_used = True

        if self.pio_num > 0:
            instance_init_used_types.update([
                Type["sysbus_add_io"],
                Type["memory_region_init_io"],
                Type["Object"],
                Type["sysbus_init_ioports"]
            ])

        for pioN in range(0, self.pio_num):
            size_macro = self.pio_size_macros[pioN]
            address_macro = self.pio_address_macros[pioN]
            instance_init_used_types.update([size_macro, address_macro])

            component = self.get_Ith_pio_id_component(pioN)

            read_func = QOMType.gen_mmio_read(
                name = self.qtn.for_id_name + "_" + component + "_read",
                struct_name = self.state_struct.name,
                type_cast_macro = self.type_cast_macro.name,
                regs = self.pio.get(pioN, None)
            )

            write_func = QOMType.gen_mmio_write(
                name = self.qtn.for_id_name + "_" + component + "_write",
                struct_name = self.state_struct.name,
                type_cast_macro = self.type_cast_macro.name,
                regs = self.pio.get(pioN, None)
            )

            write_func.extra_references = {read_func}

            self.source.add_types([read_func, write_func])

            ops_init = Initializer(
                used_types = [read_func, write_func],
                code = """{{
    .read@b=@s{read},
    .write@b=@s{write}
}}""".format(
    read = read_func.name,
    write = write_func.name
                )
            )

            ops = Type["MemoryRegionOps"](
                name = self.gen_Ith_pio_ops_name(pioN),
                pointer = False,
                initializer = ops_init,
                static = True,
                const = True
            )

            self.source.add_global_variable(ops)
            instance_init_used_globals.append(ops)

            instance_init_code += """
    memory_region_init_io(@a&s->{pio},@sobj,@s&{ops},@ss,@s{TYPE_MACRO},\
@s{size});
    sysbus_add_io(@aSYS_BUS_DEVICE(obj),@s{addr},@s&s->{pio});
    sysbus_init_ioports(@aSYS_BUS_DEVICE(obj),@s{addr},@s{size});
""".format(
    pio = self.get_Ith_io_name(pioN),
    ops = self.gen_Ith_pio_ops_name(pioN),
    TYPE_MACRO = self.qtn.type_macro,
    size = size_macro.name,
    addr = address_macro.name
            )
            s_is_used = True

        if self.out_irq_num > 0:
            instance_init_used_types.update([
                Type["qemu_irq"],
                Type["sysbus_init_irq"]
            ])

            instance_init_code += "\n"

            for irqN in range(0, self.out_irq_num):
                instance_init_code += """\
    sysbus_init_irq(@aSYS_BUS_DEVICE(obj),@s&s->%s);
""" % self.get_Ith_irq_name(irqN)

        if self.in_irq_num > 0:
            self.irq_handler = Type["qemu_irq_handler"].use_as_prototype(
                name = self.qtn.for_id_name + "_irq_handler",
                static = True,
                used_types = [
                    self.state_struct,
                    self.type_cast_macro
                ],
                body = """\
    __attribute__((unused))@b{Struct}@b*s@b=@s{UPPER}(opaque);
""".format(
    Struct = self.state_struct.name,
    UPPER = self.type_cast_macro.name,
                )
            )

            self.source.add_type(self.irq_handler)

            instance_init_code += """
    qdev_init_gpio_in(@aDEVICE(obj),@s{handler},@s{irqs});
""".format(
    handler = self.irq_handler.name,
    irqs = self.in_irq_macro.name
            )

            instance_init_used_types.update([
                self.irq_handler,
                self.in_irq_macro,
                Type["qdev_init_gpio_in"],
                Type["DEVICE"]
            ])

        self.instance_init = self.gen_instance_init_fn(self.state_struct,
            code = instance_init_code,
            s_is_used = s_is_used,
            used_types = instance_init_used_types,
            used_globals = instance_init_used_globals
        )

        self.source.add_type(self.instance_init)

        # `unrealized` method code generation
        code = ""
        used_s = False
        used_types = set([self.state_struct, self.type_cast_macro])

        if self.timer_num > 0:
            used_s = True
            code += "\n"
            used_types.update([
                Type["timer_del"],
                Type["timer_free"]
            ])

            for timerN in range(self.timer_num):
                code += """    timer_del(s->{timerN});
    timer_free(s->{timerN});
""".format(timerN = self.timer_name(timerN))

        self.device_unrealize = Function(
            name = self.qtn.for_id_name + "_unrealize",
            args = [
                Pointer(Type["DeviceState"])("dev"),
                Pointer(Pointer(Type["Error"]))("errp")
            ],
            static = True,
            used_types = used_types,
            body = """    {unused}{Struct}@b*s@b=@s{CAST}(dev);
{extra_code}""".format(
    unused = "" if used_s else "__attribute__((unused))@b",
    Struct = self.state_struct.name,
    CAST = self.type_cast_macro.name,
    extra_code = code
            )
        )
        self.source.add_type(self.device_unrealize)

        self.vmstate = self.gen_vmstate_var(self.state_struct)

        self.source.add_global_variable(self.vmstate)

        self.properties = self.gen_properties_global(self.state_struct)

        self.source.add_global_variable(self.properties)

        self.vmstate.extra_references = {self.properties}

        self.class_init = Function(
            name = "%s_class_init" % self.qtn.for_id_name,
            body = """\
    DeviceClass@b*dc@b=@sDEVICE_CLASS(oc);

    dc->realize@b@b@b=@s{dev}_realize;
    dc->reset@b@b@b@b@b=@s{dev}_reset;
    dc->unrealize@b=@s{dev}_unrealize;
    dc->vmsd@b@b@b@b@b@b=@s&vmstate_{dev};
    dc->props@b@b@b@b@b=@s{dev}_properties;
""".format(dev = self.qtn.for_id_name),
            args = [
                Pointer(Type["ObjectClass"])("oc"),
                Pointer(Type["void"])("opaque")
            ],
            static = True,
            used_types = [
                Type["DeviceClass"],
                self.device_realize,
                self.device_reset,
                self.device_unrealize
            ],
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

        type_init_usage_init = Initializer(
            code = { "function": self.register_types }
        )
        self.source.add_type(
            MacroType(Type["type_init"], initializer = type_init_usage_init)
        )

        # order life cycle functions
        self.device_realize.extra_references = {self.instance_init}
        self.device_reset.extra_references = {self.device_realize}
        self.device_unrealize.extra_references = {self.device_reset}

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
        try:
            name = self.mmio_names[i]
        except KeyError:
            desc = self.mmio.get(i, None)

            if isinstance(desc, MemoryLeafNode):
                base = desc.var_base
                name = base
            else:
                base = "mmio"
                # legacy behavior: when multiple MMIOs present then there is
                # no MMIO name without an index suffix
                if self.mmio_num == 1:
                    name = base
                else:
                    name = "%s_0" % base

            all_names = self.fields_names

            if name in all_names:
                for j in count(0):
                    name = "%s_%d" % (base, j)
                    if name not in all_names:
                        break

            self.mmio_names[i] = name

        return name

    def get_Ith_mmio_name_macro_name(self, i):
        return self.qtn.for_macros + "_" + self.get_Ith_mmio_name(i).upper()

    def get_Ith_io_name(self, i):
        if self.pio_num == 1:
            return "pio"
        else:
            return "pio_{}".format(i)
