__all__ = [
    "PCIExpressDeviceType"
]

from source import (
    line_origins,
    Pointer,
    Type,
    Function,
    Initializer,
    Macro,
    TypeNotRegistered
)
from .qom import (
    QOMDevice,
    QOMType
)
from six.moves import (
    range as xrange
)
from .pci_ids import (
    PCIVendorIdNetherExistsNorCreated,
    PCIId
)
from common import (
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
from .version import (
    get_vp
)


@describable
class PCIExpressDeviceType(QOMDevice):
    __attribute_info__ = OrderedDict([
        # Note that multiple NIC generation is not implemented yet.
        ("nic_num", { "short": _("Network interface"), "input": bool }),
        ("vendor", { "short": _("Vendor"), "input" : PCIId }),
        ("device", { "short": _("Device"), "input" : PCIId }),
        ("pci_class", { "short": _("Class"), "input" : PCIId }),
        ("subsys_vendor", { "short": _("Subsystem vendor"), "input" : PCIId }),
        ("subsys", { "short":_("Subsystem"), "input" : PCIId }),
        ("irq_num", { "short": _("IRQ pin quantity"), "input" : int }),
        ("mem_bar_num", { "short": _("BAR quantity"), "input" : int }),
        ("msi_messages_num", {
            "short": _("MSI message quantity"),
            "input" : int
        }),
        ("revision", { "short": _("Revision"), "input" : int })
    ])

    def __init__(self,
        name,
        directory,
        vendor,
        device,
        pci_class,
        irq_num = 0,
        mem_bar_num = 0,
        msi_messages_num = 0,
        revision = 0,
        subsys = None,
        subsys_vendor = None,
        bars = None,
        **qomd_kw
    ):
        super(PCIExpressDeviceType, self).__init__(name, directory, **qomd_kw)

        if get_vp("PCIE requires interface"):
            self.interfaces.add("INTERFACE_PCIE_DEVICE")
            # TODO: what about INTERFACE_CONVENTIONAL_PCI_DEVICE?

        self.irq_num = irq_num
        self.mem_bar_num = mem_bar_num
        self.msi_messages_num = msi_messages_num

        self.revision = revision

        self.vendor = vendor
        self.device = device
        self.pci_class = pci_class

        self.subsystem = subsys
        self.subsystem_vendor = subsys_vendor

        self.bars = {} if bars is None else dcp(bars)

        # Cast all PCI identifiers to PCIId
        for attr in [ "vendor", "subsystem_vendor" ]:
            val = getattr(self, attr)
            if (val is not None) and (not isinstance(val, PCIId)):
                try:
                    val = PCIId.db.get_vendor(name = val)
                except PCIVendorIdNetherExistsNorCreated:
                    val = PCIId.db.get_vendor(vid = val)
            setattr(self, attr, val)

        for attr, vendor in [
            ("device", self.vendor),
            ("subsystem", self.subsystem_vendor)
        ]:
            val = getattr(self, attr)
            if  (val is not None) and (not isinstance(val, PCIId)):
                if vendor is None:
                    raise Exception("Cannot get %s ID descriptor because of no \
corresponding vendor is given" % attr
                    )
                try:
                    val = PCIId.db.get_device(
                        name = val,
                        vendor_name = vendor.name,
                        vid = vendor.id
                    )
                except Exception:
                    val = PCIId.db.get_device(
                        did = val,
                        vendor_name = vendor.name,
                        vid = vendor.id
                    )
            setattr(self, attr, val)

        val = getattr(self, "pci_class")
        # None is not allowed there
        if not isinstance(val, PCIId):
            try:
                val = PCIId.db.get_class(name = val)
            except:
                val = PCIId.db.get_class(cid = val)
        self.pci_class = val

        self.mem_bar_size_macros = []

        self.add_state_field_h("PCIDevice", "parent_obj")

        for irqN in range(0, self.irq_num):
            self.add_state_field_h("qemu_irq", self.get_Ith_irq_name(irqN),
                save = False
            )

        for barN in xrange(0, self.mem_bar_num):
            self.add_state_field_h("MemoryRegion",
                self.get_Ith_mem_bar_name(barN),
                save = False
            )

        self.timer_declare_fields()

        self.char_declare_fields()

        self.block_declare_fields()

        self.nic_declare_fields()

    def generate_header(self):
        self.state_struct = self.gen_state()
        self.header.add_type(self.state_struct)

        self.type_name_macros = Macro(self.qtn.type_macro,
            text = '"%s"' % self.qtn.for_id_name
        )
        self.header.add_type(self.type_name_macros)

        self.type_cast_macro = Macro(self.qtn.for_macros,
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

        self.vendor_macro = self.vendor.find_macro()

        if self.subsystem_vendor and self.subsystem:
            self.subsystem_vendor_macro = self.subsystem_vendor.find_macro()
        else:
            self.subsystem_vendor_macro = None

        try:
            self.device_macro = self.device.find_macro()
        except TypeNotRegistered:
            # TODO: add device id macro to pci_ids.h
            self.header.add_type(
                Macro("PCI_DEVICE_ID_%s_%s" % (
                        self.vendor.name,
                        self.device.name
                    ),
                    text = self.device.id
                )
            )

            self.device_macro = self.device.find_macro()

        if self.subsystem_vendor and self.subsystem:
            try:
                self.subsystem_macro = self.subsystem.find_macro()
            except TypeNotRegistered:
                # TODO: add device id macro to pci_ids.h
                self.header.add_type(
                    Macro("PCI_DEVICE_ID_%s_%s" % (
                            self.subsystem_vendor.name,
                            self.subsystem.name
                        ),
                        text = self.subsystem.id
                    )
                )

                self.subsystem_macro = self.subsystem.find_macro()
        else:
            self.subsystem_macro = None

        self.pci_class_macro = self.pci_class.find_macro()

        mem_bar_def_size = 0x100

        for barN in range(0, self.mem_bar_num):
            size_macro = Macro(self.gen_Ith_mem_bar_size_macro_name(barN),
                text = "0x%X" % mem_bar_def_size
            )

            self.mem_bar_size_macros.append(size_macro)
            self.header.add_type(size_macro)

        if self.msi_messages_num > 0 :
            for_macros = self.qtn.for_macros
            self.msi_cap_offset = Macro(for_macros + "_MSI_CAP_OFFSET",
                text = "0x48"
            )
            self.msi_vectors = Macro(for_macros + "_MSI_VECTORS",
                text = "%u" % self.msi_messages_num
            )
            self.msi_64bit = Macro(for_macros + "_MSI_64BIT", text = "1")
            self.msi_masking = Macro(for_macros + "_MSI_VECTOR_MASKING",
                text = "1"
            )

            self.msi_types = [
                self.msi_cap_offset,
                self.msi_vectors,
                self.msi_64bit,
                self.msi_masking
            ]

            line_origins(self.msi_types)

            self.header.add_types(self.msi_types)

        self.gen_property_macros(self.header)

        # TODO: current value of inherit_references is dictated by Qemu coding
        # policy. Hence, version API must be used there.
        return self.header.generate(inherit_references = True)

    def generate_source(self):
        self.device_reset = Function(
            name = "%s_reset" % self.qtn.for_id_name,
            body = """\
    __attribute__((unused))@b{Struct}@b*s@b=@s{UPPER}(dev);
""".format(
    Struct = self.state_struct.name,
    UPPER = self.type_cast_macro.name,
            ),
            args = [ Pointer(Type["DeviceState"])("dev") ],
            static = True,
            used_types = [self.state_struct]
        )
        self.source.add_type(self.device_reset)

        realize_code = ''
        realize_used_types = set()
        realize_used_globals = []
        s_is_used = False

        if self.mem_bar_num > 0:
            s_is_used = True
            realize_used_types.update([
                Type["sysbus_init_mmio"],
                Type["memory_region_init_io"],
                Type["Object"]
            ])

        for barN in range(0, self.mem_bar_num):
            size_macro = self.mem_bar_size_macros[barN]
            realize_used_types.add(size_macro)

            component = self.get_Ith_mem_bar_id_component(barN)

            read_func = QOMType.gen_mmio_read(
                name = self.qtn.for_id_name + "_" + component + "_read",
                struct_name = self.state_struct.name,
                type_cast_macro = self.type_cast_macro.name,
                regs = self.bars.get(barN, None)
            )

            write_func = QOMType.gen_mmio_write(
                name = self.qtn.for_id_name + "_" + component + "_write",
                struct_name = self.state_struct.name,
                type_cast_macro = self.type_cast_macro.name,
                regs = self.bars.get(barN, None)
            )

            write_func.extra_references = {read_func}

            self.source.add_types([read_func, write_func])

            ops_init = Initializer(
                used_types = [read_func, write_func],
                code = """{{
    .read = {read},
    .write = {write}
}}""".format(
    read = read_func.name,
    write = write_func.name
                )
            )

            ops = Type["MemoryRegionOps"](
                name = self.gen_Ith_mem_bar_ops_name(barN),
                pointer = False,
                initializer = ops_init,
                static = True
            )

            self.source.add_global_variable(ops)
            realize_used_globals.append(ops)

            realize_code += """
    memory_region_init_io(@a&s->{bar},@sOBJECT(dev),@s&{ops},@ss,@s{TYPE_MACRO},@s{size});
    pci_register_bar(@a&s->parent_obj,@s{barN},@sPCI_BASE_ADDRESS_SPACE_MEMORY,@s&s->{bar});
""".format(
    barN = barN,
    bar = self.get_Ith_mem_bar_name(barN),
    ops = self.gen_Ith_mem_bar_ops_name(barN),
    TYPE_MACRO = self.qtn.type_macro,
    size = size_macro.name
            )

        if self.msi_messages_num > 0 :
            msi_init_type = Type["msi_init"]
            s_is_used = True

            realize_code += """
    msi_init(dev,@s%s,@s%s,@s%s,@s%s%s);
""" % (self.msi_cap_offset.gen_usage_string(),
       self.msi_vectors.gen_usage_string(),
       self.msi_64bit.gen_usage_string(),
       self.msi_masking.gen_usage_string(),
       ",@serrp" if msi_init_type.args[-1].type \
                   == Pointer(Pointer(Type["Error"])) else ""
            )

            realize_used_types.update(self.msi_types)
            realize_used_types.add(msi_init_type)

        self.device_realize = self.gen_realize("PCIDevice",
            code = realize_code,
            s_is_used = s_is_used,
            used_types = realize_used_types,
            used_globals = realize_used_globals
        )
        self.source.add_type(self.device_realize)

        code = ""
        used_types = set([self.state_struct])
        used_s = False

        if self.msi_messages_num > 0:
            code += """
    msi_uninit(dev);
"""
            used_types.add(Type["msi_uninit"])

        if self.nic_num > 0:
            code += "\n"
            used_s = True

            del_nic = Type["qemu_del_nic"]
            used_types.add(del_nic)

            for nicN in xrange(self.nic_num):
                nic_name = self.nic_name(nicN)
                code += "    %s(s->%s);\n" % (del_nic.name, nic_name)

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
""".format(
    timerN = self.timer_name(timerN)
                )

        self.device_exit = Function(
            name = "%s_exit" % self.qtn.for_id_name,
            args = [ Pointer(Type["PCIDevice"])("dev") ],
            static = True,
            used_types = used_types,
            body = """\
    {unused}{Struct}@b*s@b=@s{UPPER}(dev);
{extra_code}\
""".format(
    unused = "" if used_s else "__attribute__((unused))@b",
    Struct = self.state_struct.name,
    UPPER = self.type_cast_macro.name,
    extra_code = code
            )
        )
        self.source.add_type(self.device_exit)

        self.vmstate = self.gen_vmstate_var(self.state_struct)

        self.source.add_global_variable(self.vmstate)

        self.properties = self.gen_properties_global(self.state_struct)

        self.source.add_global_variable(self.properties)

        self.vmstate.extra_references = {self.properties}

        self.class_init = Function(
            name = "%s_class_init" % self.qtn.for_id_name, 
            body = """\
    DeviceClass@b*dc@b=@sDEVICE_CLASS(oc);
    PCIDeviceClass@b*pc@b=@sPCI_DEVICE_CLASS(oc);

    pc->realize@b@b@b{pad}=@s{dev}_realize;
    dc->reset@b@b@b@b@b{pad}=@s{dev}_reset;
    pc->exit@b@b@b@b@b@b{pad}=@s{dev}_exit;
    pc->vendor_id@b{pad}=@s{vendor_macro};
    pc->device_id@b{pad}=@s{device_macro};
    pc->class_id@b@b{pad}=@s{pci_class_macro};{subsys_id}{subsys_vid}
    pc->revision@b@b{pad}=@s{revision};
    dc->vmsd@b@b@b@b@b@b{pad}=@s&vmstate_{dev};
    dc->props@b@b@b@b@b{pad}=@s{dev}_properties;
""".format(
    dev = self.qtn.for_id_name,
    revision = self.revision,
    vendor_macro = self.vendor_macro.name,
    device_macro = self.device_macro.name,
    pci_class_macro = self.pci_class_macro.name,
    subsys_id = '' if self.subsystem_macro is None else ("""
    pc->subsystem_id@b@b@b@b@b@b@b@b=@s%s;""" % self.subsystem_macro.name),
    subsys_vid = '' if self.subsystem_vendor_macro is None else ("""
    pc->subsystem_vendor_id@b=@s%s;""" % self.subsystem_vendor_macro.name),
    pad = '@b@b@b@b@b@b@b@b@b@b' if self.subsystem_vendor_macro else ''
            ),
            args = [
                Pointer(Type["ObjectClass"])("oc"),
                Pointer(Type["void"])("opaque")
            ],
            static = True,
            used_types = [
                Type["DeviceClass"],
                Type["PCIDeviceClass"],
                self.device_realize,
                self.device_reset,
                self.device_exit,
                self.vendor_macro,
                self.device_macro,
                self.pci_class_macro
            ],
            used_globals = [
                self.vmstate,
                self.properties
            ]
        )
        self.source.add_type(self.class_init)

        instance_init_used_types = set()
        instance_init_code = ""
        s_is_used = False

        self.instance_init = self.gen_instance_init_fn(self.state_struct,
            code = instance_init_code,
            s_is_used = s_is_used,
            used_types = instance_init_used_types
        )
        self.source.add_type(self.instance_init)

        self.type_info = self.gen_type_info_var(self.state_struct,
            self.instance_init, self.class_init,
            parent_tn = "TYPE_PCI_DEVICE"
        )

        self.source.add_global_variable(self.type_info)

        self.register_types = self.gen_register_types_fn(self.type_info)

        self.source.add_type(self.register_types)

        type_init_usage_init = Initializer(
            code = { "function": self.register_types }
        )
        self.source.add_type(
            Type["type_init"].gen_usage(initializer = type_init_usage_init)
        )

        # order life cycle functions
        self.device_reset.extra_references = {self.device_realize}
        self.device_exit.extra_references = {self.device_reset}

        return self.source.generate()

    def get_Ith_mem_bar_id_component(self, i):
        return self.get_Ith_mem_bar_name(i)

    def gen_Ith_mem_bar_size_macro_name(self, i):
        UPPER = self.get_Ith_mem_bar_id_component(i).upper()
        return "%s_%s_SIZE" % (self.qtn.for_macros, UPPER)

    def gen_Ith_mem_bar_ops_name(self, i):
        return self.qtn.for_id_name + "_" \
            + self.get_Ith_mem_bar_id_component(i) + "_ops"

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
