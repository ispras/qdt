__all__ = [
    "get_vp"
]

from hashlib import (
    md5
)
from source import (
    Initializer,
    add_base_types,
    Pointer,
    Header,
    Type,
    Function,
    Macro,
    Enumeration,
    Structure
)

from os.path import (
    sep
)

# Callable
def c(value):
    return globals()[value]

# Basic
def b(value):
    return value

# QEMU Version Heuristic Dictionary
class QVHDict(dict):
    def __setitem__(self, key, value):
        if callable(value):
            super(QVHDict, self).__setitem__(key, ("c", value.__name__))
        else:
            super(QVHDict, self).__setitem__(key, ("b", value))

    def __getitem__(self, key):
        converter, value = super(QVHDict, self).__getitem__(key)
        return c(converter)(value)

class QEMUVersionParameterDescription(object):
    def __init__(self, name, new_value = None, old_value = None):
        if new_value is None and old_value is None:
            raise ValueError("Attempt to create heuristic '%s' with None as "
                "both values." % name
            )
        self.name = name
        self.new_value = new_value
        self.old_value = old_value

    # modification detection code
    def gen_mdc(self):
        if callable(self.new_value):
            nv = self.new_value.__name__
        else:
            nv = str(self.new_value)

        if callable(self.old_value):
            ov = self.old_value.__name__
        else:
            ov = str(self.old_value)

        return self.name + nv + ov

def define_only_qemu_2_6_0_types():
    # According to Qemu inclusion policy, each source file must include
    # qemu/osdep.h. This could be met using different ways. For now add a
    # reference to a fake type inside osdep.h.
    # TODO: the tweak must be handled using version API.
    osdep_fake_type = Type("FAKE_TYPE_IN_QEMU_OSDEP")

    if not get_vp("tcg_enabled is macro"):
        Header["qemu-common.h"].add_types([
            Function(
                name = "tcg_enabled",
                ret_type = Type["bool"]
            )
        ])

    Header["tcg.h"].add_types([
        Type("TCGv_i32"),
        Type("TCGv_i64"),
        Type("TCGv_ptr"),
        Type("TCGv_env"),
        Type("TCGv"),
        Function(name = "tcg_global_mem_new_i32"),
        Function(name = "tcg_global_mem_new_i64"),
        Function(name = "tcg_op_buf_full")
    ])

    Header["tcg-op.h"].add_types([
        Function(name = "tcg_gen_insn_start"),
        Function(name = "tcg_gen_goto_tb"),
        Function(name = "tcg_gen_exit_tb")
    ])

    Header["tcg-op.h"].add_types([
        # HLTTemp is a fake type intended to mark
        # variables which are to be replaced by this tool
        # preprocessor (still in progress)
        # HLTTemp is then converted to some existing QEMU types
        Type("HLTTemp")
    ])

    Header["qemu/osdep.h"].add_types([
        osdep_fake_type
    ])

    Header["exec/hwaddr.h"].add_types([
        Type("hwaddr", False)
    ]).add_reference(osdep_fake_type)

    Header["exec/cpu-defs.h"].add_types([
        Type("target_ulong", False)
    ])

    Header["exec/cpu_ldst.h"].add_types([
        Function(name = "cpu_ldub_code", ret_type = Type["uint8_t"]),
        Function(name = "cpu_lduw_code", ret_type = Type["uint16_t"]),
        Function(name = "cpu_ldl_code", ret_type = Type["uint32_t"]),
        Function(name = "cpu_ldq_code", ret_type = Type["uint64_t"]),
    ])

    Header["qom/object.h"].add_types([
        Type("ObjectClass", False),
        Type("Object", False),
        Type("InterfaceInfo", False),
        Structure("TypeInfo",
            # These are required fields only
            Pointer(Type["const char"])("name"),
            Pointer(Type["const char"])("parent"),
            Pointer(Type["void"])("class_init"),
            Pointer(Type["InterfaceInfo"])("interfaces")
        ),
        Type("Type", False),
        Type("TypeImpl", False),
        Function(
            name = "type_register_static",
            ret_type = Type["TypeImpl"],
            args = [ Pointer(Type["TypeInfo"])("info") ]
        ),
        Function(
            name = "type_register",
            ret_type = Type["TypeImpl"],
            args = [ Pointer(Type["TypeInfo"])("info") ]
        ),
        Function(name = "object_get_typename"),
        Function(name = "object_property_set_str"),
        Function(name = "object_property_set_link"),
        Function(name = "object_property_set_bool"),
        Function(name = "object_property_set_int"),
        Function(name = "object_class_by_name"),
        Function(name = "object_class_dynamic_cast"),
        Function(name = "object_class_is_abstract")
    ]).add_reference(osdep_fake_type)

    Header["qom/cpu.h"].add_types([
        Type("CPUState", False),
        Type("CPUClass", False),
        Type("vaddr", False),
        Type("MMUAccessType", False),
        Type("CPUBreakpoint", False),
        Function(
            name = "qemu_init_vcpu",
            args = [ Pointer(Type["CPUState"])("cpu") ]
        ),
        Function(name = "cpu_exec_realizefn"),
        Function(name = "cpu_reset"),
        Function(name = "cpu_create"),
        Function(name = "cpu_generic_init")
    ]).add_reference(osdep_fake_type)

    Header["qapi/error.h"].add_types([
        Structure("Error")
    ]).add_reference(osdep_fake_type)

    # Move typedefs.h upper forcing headers below to use declarations from it
    Header["qemu/typedefs.h"].add_types([
        Type["Error"].gen_forward_declaration(),
        # BlockBackend is defined in internal block_int.h. Its fields may not
        # be accessed outside internal code. Methods from block-backend.h must
        # be used instead.
        Structure("BlockBackend"),
        Structure("I2CBus") # the structure is defined in .c file
    ]).add_reference(osdep_fake_type)

    Header[get_vp("disas header")].add_types([
        Type("disassemble_info", False)
    ]).add_reference(osdep_fake_type)

    Header[get_vp("fprintf_function definer")].add_types([
        Type("fprintf_function", False)
    ]).add_reference(osdep_fake_type)

    Header["exec/exec-all.h"].add_types([
        Type("TranslationBlock", False),
        Function(
            name = "tlb_fill",
            args = [
                Pointer(Type["CPUState"])("cs"),
                Type["target_ulong"]("addr"),
                Type["MMUAccessType"]("access_type"),
                Type["int"]("mmu_idx"),
                Type["uintptr_t"]("retaddr")
            ],
            used_types = []
        ),
        Function(
            name = "cpu_exec_init",
            args = [
                Pointer(Type["CPUState"])("cs"),
                Pointer(Pointer(Type["Error"]))("errp")
            ]
        ),
        Function(name = "gen_intermediate_code"),
        Function(name = "cpu_restore_state"),
        Function(name = "cpu_loop_exit"),
        Function(name = "cpu_loop_exit_restore"),
        Function(name = "tlb_set_page")
    ]).add_reference(osdep_fake_type)

    Header["exec/gen-icount.h"].add_types([
        Function(name = "gen_tb_start"),
        Function(name = "gen_tb_end")
    ])

    Header["exec/address-spaces.h"].add_types([
        Function(name = "get_system_memory")
    ]).add_reference(osdep_fake_type)

    Header["exec/memory.h"].add_types([
        Type("MemoryRegion", False),
        Function(
            name = "MemoryRegionOps_read",
            ret_type = Type["uint64_t"],
            args = [
                Pointer(Type["void"])("opaque"),
                Type["hwaddr"]("offset"),
                Type["unsigned"]("size")
            ]
        ),
        Function(
            name = "MemoryRegionOps_write",
            ret_type = Type["void"],
            args = [
                Pointer(Type["void"])("opaque"),
                Type["hwaddr"]("offset"),
                Type["uint64_t"]("value"),
                Type["unsigned"]("size")
            ]
        ),
        Structure("MemoryRegionOps",
            Type["MemoryRegionOps_read"]("read"),
            Type["MemoryRegionOps_write"]("write"),
        ),
        Function(
            name = "memory_region_init_io",
            args = [
                Pointer(Type["MemoryRegion"])("mr"),
                # struct
                Pointer(Type["Object"])("owner"),
                # const
                Pointer(Type["MemoryRegionOps"])("ops"),
                Pointer(Type["void"])("opaque"),
                Pointer(Type["const char"])("name"),
                Type["uint64_t"]("size")
            ]
        ),
        Function(name = "memory_region_init"),
        Function(name = "memory_region_init_alias"),
        Function(name = "memory_region_init_ram"),
        Function(name = "memory_region_init_rom_device"),
        Function(name = "memory_region_add_subregion_overlap"),
        Function(name = "memory_region_add_subregion")
    ]).add_reference(osdep_fake_type)

    Header["exec/gdbstub.h"].add_types([
        Function(name = "gdb_get_reg8"),
        Function(name = "gdb_get_reg16"),
        Function(name = "gdb_get_reg32"),
        Function(name = "gdb_get_reg64")
    ]).add_reference(osdep_fake_type)

    ioport_header = Header["exec/ioport.h"].add_reference(osdep_fake_type)
    if get_vp("pio_addr_t exists"):
        ioport_header.add_types([
            Type("pio_addr_t", incomplete = False)
        ])

    Header["hw/boards.h"].add_types([
        Structure("MachineClass"),
        Structure("MachineState")
    ]).add_reference(osdep_fake_type)

    pio_t = Type["pio_addr_t" if get_vp("pio_addr_t exists") else "uint32_t"]
    Header["hw/sysbus.h"].add_types([
        Type("SysBusDevice", False),
        Type("qemu_irq", False),
        Function(
            name = "sysbus_init_mmio",
            ret_type = Type["void"],
            args = [
                Pointer(Type["SysBusDevice"])("dev"),
                Pointer(Type["MemoryRegion"])("memory")
            ]
        ),
        Function(
            name = "sysbus_init_irq",
            ret_type = Type["void"],
            args = [
                Pointer(Type["SysBusDevice"])("dev"),
                Pointer(Type["qemu_irq"])("p")
            ]
        ),
        Function(
            name = "sysbus_add_io",
            ret_type = Type["void"],
            args = [
                Pointer(Type["SysBusDevice"])("dev"),
                Type["hwaddr"]("addr"),
                Pointer(Type["MemoryRegion"])("mem")
            ]
        ),
        Function(
            name = "sysbus_init_ioports",
            ret_type = Type["void"],
            args = [
                Pointer(Type["SysBusDevice"])("dev"),
                pio_t("ioport"),
                pio_t("size")
            ]
        ),
        Function(name = "sysbus_mmio_map"),
        Function(name = "sysbus_connect_irq")
    ]).add_reference(osdep_fake_type)

    Header["hw/irq.h"].add_types([
        Function(
            name = "qemu_irq_handler",
            ret_type = Type["void"],
            args = [
                Pointer(Type["void"])("opaque"),
                Type["int"]("n"),
                Type["int"]("level")
            ]
        ),
        Function(name = "qemu_irq_split")
    ]).add_reference(osdep_fake_type)

    Header["hw/qdev-core.h"].add_types([
        Type("DeviceClass", False),
        Type("DeviceState", False),
        Type("Property", False),
        Function(
            name = "qdev_init_gpio_in",
            ret_type = Type["void"],
            args = [
                Pointer(Type["DeviceState"])("dev"),
                Type["qemu_irq_handler"]("handler"),
                Type["int"]("n")
            ]
        ),
        Pointer(
            Function("device_realize pointee",
                args = [
                    Pointer(Type["DeviceState"])("dev"),
                    Pointer(Pointer(Type["Error"]))("errp")
                ]
            ),
            name = "DeviceRealize",
        ),
        Function(name = "qdev_create"),
        Function(name = "qdev_init_nofail"),
        Function(name = "qdev_get_child_bus"),
        Structure("BusState"),
        Function(name = "qdev_get_gpio_in"),
        Function(name = "qdev_get_gpio_in_named"),
        Function(name = "qdev_connect_gpio_out"),
        Function(name = "qdev_connect_gpio_out_named")
    ]).add_reference(osdep_fake_type)

    Header["migration/vmstate.h"].add_types([
        Type("VMStateDescription", False),
        Type("VMStateField", False),
        Function(name = "vmstate_register_ram_global")
    ]).add_reference(osdep_fake_type)

    Header["qemu/module.h"].add_reference(osdep_fake_type)

    Header["hw/pci/pci.h"].add_types([
        Type("PCIDevice", False),
        Type("PCIDeviceClass", False),
        Function(name = "pci_create_multifunction"),
        Type("PCIIOMMUFunc"),
    ]).add_reference(osdep_fake_type)

    Header["hw/pci/msi.h"].add_types([
        Function(
            name = "msi_uninit",
            ret_type = Type["void"],
            args = [ Pointer(Type["PCIDevice"])("dev") ]
        )
    ]).add_reference(osdep_fake_type)

    Header["hw/pci/pci_bus.h"].add_types([
        Type("PCIBus", incomplete = True)
    ]).add_references([
        Type["PCIIOMMUFunc"],
        osdep_fake_type
    ])
    Header["hw/pci/pci_host.h"].add_reference(osdep_fake_type)

    Header["qemu/bswap.h"].add_types([
        Function(name = "bswap64"),
        Function(name = "bswap32"),
        Function(name = "bswap16")
    ]).add_reference(osdep_fake_type)

    Header["hw/ide/internal.h"].add_types([
        Structure("IDEDMA")
    ]).add_reference(osdep_fake_type)

    Header["hw/ide/ahci.h"].add_references([
        Type["IDEDMA"],
        osdep_fake_type
    ])

    Header["hw/block/flash.h"].add_references([
        Type["VMStateDescription"],
        osdep_fake_type
    ])

    Header["qemu/timer.h"].add_types([
        Structure("QEMUTimer"),
        Function(name = "timer_new_ns"),
        Function(name = "timer_del"),
        Function(name = "timer_free"),
        # These are required elements only
        Enumeration([("QEMU_CLOCK_VIRTUAL", 1)],
            typedef_name = "QEMUClockType"
        )
    ]).add_references([
        osdep_fake_type
    ])

    Header["qemu/main-loop.h"].add_types([
        Function(
            name = "IOCanReadHandler",
            ret_type = Type["int"],
            args = [ Pointer(Type["void"])("opaque") ]
        ),
        Function(
            name = "IOReadHandler",
            args = [
                Pointer(Type["void"])("opaque"),
                Pointer(Type["uint8_t"])("buf", const = True),
                Type["int"]("size")
            ]
        )
    ]).add_references([
        osdep_fake_type
    ])

    if get_vp("v2.8 chardev"):
        chardev_types = [
            Function(name = "qemu_chr_fe_set_handlers"),
            Structure("CharBackend")
        ]
    else:
        chardev_types = [
            Function(name = "qemu_chr_add_handlers"),
            Structure("CharDriverState")
        ]

    Header[get_vp("header with IOEventHandler")].add_types([
        Function(
            name = "IOEventHandler",
            args = [
                Pointer(Type["void"])("opaque"),
                Type["int"]("event")
            ]
        )
    ] + chardev_types).add_references([
        osdep_fake_type
    ])

    Header["sysemu/block-backend.h"].add_types([
        Structure("BlockDevOps")
    ]).add_references([
        osdep_fake_type
    ])

    Header["hw/isa/isa.h"].add_types([
        Type("IsaDmaTransferHandler")
    ])

    if get_vp("include/hw/isa/i8257.h have IsaDmaTransferHandler reference"):
        Header[get_vp("i8257.h path")].add_references([
            Type["IsaDmaTransferHandler"],
            Type["MemoryRegion"]
        ])

    Header["qapi/qapi-types-net.h"].add_types([
        # The value is taken from a auto generated file and may change in the
        # future.
        Enumeration([("NET_CLIENT_DRIVER_NIC", 1)],
            enum_name = "NetClientDriver",
            typedef_name = "NetClientDriver"
        )
    ])

    Header["net/net.h"].add_types([
        Type("qemu_macaddr_default_if_unset"),
        Type("qemu_format_nic_info_str"),
        Type("qemu_new_nic"),
        Type("qemu_del_nic"),
        Type("qemu_get_queue"),
        Structure("NICConf"),
        Type("NICState"),
        Type("NetClientState"),
        Function(
            name = "NetCanReceive",
            ret_type = Type["int"],
            args = [ Pointer(Type["NetClientState"])("nc") ]
        ),
        Function(
            name = "NetReceive",
            ret_type = Type["ssize_t"],
            args = [
                Pointer(Type["NetClientState"])("nc"),
                Pointer(Type["const uint8_t"])("buf"),
                Type["size_t"]("size")
            ]
        ),
        Function(
            name = "LinkStatusChanged",
            args = [ Pointer(Type["NetClientState"])("nc") ]
        ),
        Function(
            name = "NetCleanup",
            args = [ Pointer(Type["NetClientState"])("nc") ]
        ),
        Structure("NetClientInfo",
            # These are required fields only
            Type["NetClientDriver"]("type"),
            Type["size_t"]("size"),
            Type["NetReceive"]("receive"),
            Type["NetCanReceive"]("can_receive"),
            Type["NetCleanup"]("cleanup"),
            Type["LinkStatusChanged"]("link_status_changed")
        ),
    ]).add_references([
        osdep_fake_type
    ])

    Header[get_vp("disas header")].add_types([
        Type("bfd_vma", False),
        Type("bfd_byte", False)
    ])

    Header[get_vp("disas header")].add_types([
        Function(
            name = name,
            ret_type = Type["bfd_vma"],
            args = [ Pointer(Pointer(Type["bfd_byte"]))("addr", const = True) ]
        ) for name in ["bfd_getl64", "bfd_getl32", "bfd_getb32", "bfd_getl16",
            "bfd_getb16"
        ]
    ])

    Header["disas/disas.h"].add_types([
        Function(name = "lookup_symbol")
    ])

    Header["qemu/log.h"].add_types([
        Function(name = "qemu_loglevel_mask"),
        Function(name = "qemu_log_in_addr_range"),
        Function(name = "qemu_log_lock"),
        Function(name = "qemu_log_unlock"),
        Function(name = "qemu_log")
    ])

    Header["exec/log.h"].add_types([
        Function(name = "log_target_disas")
    ])

    Header["sysemu/reset.h"].add_types([
        # XXX: It's neither a function nor a function pointer. It's something
        # between.
        Function(name = "QEMUResetHandler",
            ret_type = Type["void"],
            args = [ Pointer(Type["void"])("opaque") ]
        ),
        Function(name = "qemu_register_reset")
    ])

def define_qemu_2_6_5_types():
    add_base_types()
    define_only_qemu_2_6_0_types()

    if get_vp("char backend hotswap handler"):
        Header["chardev/char-fe.h"].add_type(
            Function(
                name = "BackendChangeHandler",
                ret_type = Type["int"],
                args = [ Pointer(Type["void"])("opaque") ]
            )
        )

def define_qemu_2_6_0_types():
    add_base_types()
    # The paths of the headers are presented relative root directory.
    Header("hw/ide/internal.h")
    Header("hw/ide/ahci.h")
    define_only_qemu_2_6_0_types()

def define_msi_init_2_6_5():
    Header["hw/pci/msi.h"].add_type(
        Function(
            name = "msi_init",
            ret_type = Type["int"],
            args = [
                Pointer(Type["PCIDevice"])("dev"),
                Type["uint8_t"]("offset"),
                Type["unsigned int"]("nr_vectors"),
                Type["bool"]("msi64bit"),
                Type["bool"]("msi_per_vector_mask"),
                Pointer(Pointer(Type["Error"]))("errp")
            ]
        )
    )

def define_msi_init_2_6_0():
    Header["hw/pci/msi.h"].add_type(
        Function(
            name = "msi_init",
            ret_type = Type["int"],
            args = [
                Pointer(Type["PCIDevice"])("dev"),
                Type["uint8_t"]("offset"),
                Type["unsigned int"]("nr_vectors"),
                Type["bool"]("msi64bit"),
                Type["bool"]("msi_per_vector_mask")
            ]
        )
    )

def machine_register_2_5(mach):
    # machine class definition function
    mach.class_init = Function(
        name = "machine_%s_class_init" % mach.qtn.for_id_name,
        static = True,
        ret_type = Type["void"],
        args = [
            Pointer(Type["ObjectClass"])("oc"),
            Pointer(Type["void"])("opaque")
        ],
        body = """\
    MachineClass *mc = MACHINE_CLASS(oc);

    mc->name = \"{type_name}\";
    mc->desc = \"{desc}\";
    mc->init = {instance_init};
""".format(
    type_name = mach.qtn.for_id_name,
    desc = mach.desc,
    instance_init = mach.instance_init.name
        ),
        used_types = [
            Type["MachineClass"],
            Type["MACHINE_CLASS"],
            mach.instance_init
        ]
    )
    mach.source.add_type(mach.class_init)

    # machine type definition structure
    type_machine_macro = Type["TYPE_MACHINE"]
    type_machine_suf_macro = Type["TYPE_MACHINE_SUFFIX"]

    mach.type_info = Type["TypeInfo"](
        name = "machine_type_%s" % mach.qtn.for_id_name,
        static = True,
        initializer = Initializer({
                "name" : '"%s" %s' % (mach.qtn.for_id_name,
                    type_machine_suf_macro.name
                ),
                "parent" : type_machine_macro,
                "class_init" : mach.class_init
            },
            used_types = [ type_machine_suf_macro ]
        )
    )
    mach.source.add_global_variable(mach.type_info)

    # machine type registration function
    mach.type_reg_func = Function(
        name = "machine_init_%s" % mach.qtn.for_id_name,
        body = """\
    type_register(&{type_info});
""".format(type_info = mach.type_info.name),
        static = True,
        used_types = [Type["type_register"]],
        used_globals = [mach.type_info]
    )
    mach.source.add_type(mach.type_reg_func)

    # Main machine registration macro
    def_type = get_vp("machine initialization function register type name")
    machine_init_def_args = Initializer(
        code = { "function": mach.type_reg_func }
    )
    mach.source.add_type(
        Type[def_type].gen_usage(
            initializer = machine_init_def_args
        )
    )

def machine_register_2_6(mach):
    # machine class definition function
    mach.class_init = Function(
        name = "machine_%s_class_init" % mach.qtn.for_id_name,
        static = True,
        ret_type = Type["void"],
        args = [
            Pointer(Type["ObjectClass"])("oc"),
            Pointer(Type["void"])("opaque")
        ],
        body = """\
    MachineClass *mc = MACHINE_CLASS(oc);

    mc->desc = \"{desc}\";
    mc->init = {instance_init};
""".format(
    desc = mach.desc,
    instance_init = mach.instance_init.name
        ),
        used_types = [
            Type["MachineClass"],
            Type["MACHINE_CLASS"],
            mach.instance_init
        ]
    )
    mach.source.add_type(mach.class_init)

    # machine type definition structure
    type_machine_macro = Type["TYPE_MACHINE"]
    type_machine_type_name_macro = Type["MACHINE_TYPE_NAME"]

    mach.type_info = Type["TypeInfo"](
        name = "machine_type_%s" % mach.qtn.for_id_name,
        static = True,
        initializer = Initializer({
                "name" : type_machine_type_name_macro.gen_usage_string(
                    Initializer({
                        "machinename" : '"%s"' % mach.qtn.for_id_name
                    })
                ),
                "parent" : type_machine_macro,
                "class_init" : mach.class_init
            },
            used_types = [ type_machine_type_name_macro ]
        )
    )
    mach.source.add_global_variable(mach.type_info)

    # machine type registration function
    mach.type_reg_func = mach.gen_register_types_fn(mach.type_info)
    mach.source.add_type(mach.type_reg_func)

    # Main machine registration macro
    machine_init_def_args = Initializer({ "function": mach.type_reg_func })
    mach.source.add_type(
        Type["type_init"].gen_usage(
            initializer = machine_init_def_args
        )
    )

qemu_heuristic_db = {
    # Next two commits precede v4.1.0-rc0. They are in one branch.
    u'ede9a8a656c992deecce45f8175985dd81cc6be9' : [
        QEMUVersionParameterDescription("fprintf_function definer",
            new_value = "disas/dis-asm.h",
            old_value = "qemu/fprintf-fn.h"
        )
    ],
    u'3979fca4b69fc31c372687cd0bb6950592f248bd' : [
        QEMUVersionParameterDescription("disas header",
            new_value = "disas/dis-asm.h",
            old_value = "disas/bfd.h"
        )
    ],
    u'b59821a95bd1d7cb4697fd7748725c910582e0e7' : [
        QEMUVersionParameterDescription("explicit global memory registration",
            new_value = False,
            old_value = True
        )
    ],
    u'2fefa16cec5a719f5cbc26c0672dd2099cd2ed9b' : [
        QEMUVersionParameterDescription("PCIE requires interface",
            new_value = True,
            old_value = False
        )
    ],
    u'81517ba37a6cec59f92396b4722861868eb0a500' : [
        QEMUVersionParameterDescription("char backend hotswap handler",
            new_value = True,
            old_value = False
        )
    ],
    # hw: remove pio_addr_t
    u'89a80e7400f7225d9401b35ef32454b4ab29dc67' : [
        QEMUVersionParameterDescription("pio_addr_t exists",
            new_value = False,
            old_value = True
        )
    ],
    u'fcf5ef2ab52c621a4617ebbef36bf43b4003f4c0' : [
        # This commit moves target-* CPU file into a target/ folder
        # So target-xxx/ becomes target/xxx/ instead.
        QEMUVersionParameterDescription("target folder",
            new_value = "target" + sep,
            old_value = "target-"
        )
    ],
    u'0e6aac87fd0f5db2be57c36c03d67388577208a7' : [
        # It is actually last commit touching the way of machine registration.
        # There is no reason to make more fine grained history decomposition.
        QEMUVersionParameterDescription(
            "machine type register template generator",
            new_value = machine_register_2_6,
            old_value = machine_register_2_5
        )
    ],
    u'82878dac6fcd16cb4fa47266bcd3dd03df436dae' : [
        # It is the last commit in the series significantly changing char API.
        QEMUVersionParameterDescription("v2.8 chardev",
            new_value = True,
            old_value = False
        )
    ],
    u'bd36a618ccb61ea0fddb92e75f3754c4e1a7fbfe' : [
        # This commit renames DMA_transfer_handler to IsaDmaTransferHandler
        # adding the corresponding reverence.
        QEMUVersionParameterDescription(
            "include/hw/isa/i8257.h have IsaDmaTransferHandler reference",
            new_value = True,
            old_value = False
        )
    ],
    u'f5f19ee2e448a8442f1974ca1a0b8864486ed25b': [
        # Q35 for 2.6 uses I8257 for DMA. The device could be used after
        # patch series followed by commit of the SHA1.
        QEMUVersionParameterDescription("QDC default project class name",
            new_value = "Q35Project_2_6_0",
            old_value = "Q35Project_2_5_0"
        )
    ],
    u'8c4575472494a5dfedfe05e7b58ca9ce3872ad56':
    [
        QEMUVersionParameterDescription(
            "machine initialization function register type name",
            new_value = "type_init",
            old_value = "machine_init"
        )
    ],
    u'e8ad4d16808690e9c0d68b140218ca466c9309fc':
    [
        QEMUVersionParameterDescription("qemu types definer",
            new_value = define_qemu_2_6_5_types,
            old_value = define_qemu_2_6_0_types,
        )
    ],
    u'1108b2f8a939fb5778d384149e2f1b99062a72da':
    [
        QEMUVersionParameterDescription("msi_init type definer",
            new_value = define_msi_init_2_6_5,
            old_value = define_msi_init_2_6_0
        )
    ],
    u'4d43a603c71d0eb92534bc82b72933f329d8a64c':
    [
        QEMUVersionParameterDescription("header with IOEventHandler",
            new_value = "chardev/char-fe.h",
            old_value = "sysemu/char.h"
        )
    ],
    u'8e2b72990e9dc80ab3ff19717f45fec839bbcbc2':
    [
        QEMUVersionParameterDescription("tcg_enabled is macro",
            new_value = True,
            old_value = False
        )
    ],
    u'55f613ac25420384b2c4645420fea2f9bab15379':
    [
        # Be aware of moving 'i8257.h' header from hw/isa/ to hw/dma/
        QEMUVersionParameterDescription("i8257.h path",
            new_value = "hw/dma/i8257.h",
            old_value = "hw/isa/i8257.h"
        )
    ],
    u'1c2adb958fc07e5b3e81ed21b801c04a15f41f4f':
    [
        # cpu_env initialization was moved to common code in QEMU in this
        # commit. Hence we have to decide if such initialization function
        # must be generated by our system
        QEMUVersionParameterDescription("Init cpu_env in arch",
            old_value = True,
            new_value = False
        )
    ]
}

version_parameters = None

# calculate hash of qemu_heuristic_db
def calculate_qh_hash():
    vd_h = md5()
    for k in sorted(qemu_heuristic_db):
        for v in qemu_heuristic_db[k]:
            vd_h.update(str(k + v.gen_mdc()).encode('utf-8'))

    return vd_h.hexdigest()

def initialize_version(qvh_vp):
    global version_parameters
    version_parameters = {}
    for k in qvh_vp.keys():
        version_parameters[k] = qvh_vp[k]

def get_vp(heuristic_name = None):
    if heuristic_name is None: # legacy behaviour
        return version_parameters
    else:
        return version_parameters[heuristic_name]

