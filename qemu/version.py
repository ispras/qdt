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
    Structure
)

from os.path import \
    sep

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
        Header.lookup("qemu-common.h").add_types([
            Function("tcg_enabled",
                     ret_type = Type.lookup("bool")
            )
        ])

    Header.lookup("tcg.h").add_types([
        Type("TCGv_i32"),
        Type("TCGv_i64"),
        Type("TCGv_ptr"),
        Type("TCGv_env", incomplete = False),
        Type("TCGv"),
        Function("tcg_global_mem_new_i32"),
        Function("tcg_global_mem_new_i64"),
        Function("tcg_op_buf_full")
    ])

    cpu_env = Type.lookup("TCGv_env").gen_var("cpu_env")
    Header.lookup("tcg.h").add_global_variable(cpu_env)

    Header.lookup("tcg-op.h").add_types([
        Function("tcg_gen_insn_start"),
        Function("tcg_gen_goto_tb"),
        Function("tcg_gen_exit_tb")
    ])

    Header.lookup("tcg-op.h").add_types([
        Type("HLTTemp")
    ])

    Header.lookup("qemu/osdep.h").add_types([
        osdep_fake_type
    ])

    Header.lookup("exec/hwaddr.h").add_types([
        Type("hwaddr", False)
    ]).add_reference(osdep_fake_type)

    Header.lookup("exec/cpu-defs.h").add_types([
        Type("target_ulong", False),
    ])

    Header.lookup("exec/cpu_ldst.h").add_types([
        Function("cpu_ldub_code", ret_type = Type.lookup("uint8_t")),
        Function("cpu_lduw_code", ret_type = Type.lookup("uint16_t")),
        Function("cpu_ldl_code", ret_type = Type.lookup("uint32_t")),
        Function("cpu_ldq_code", ret_type = Type.lookup("uint64_t")),
    ])

    Header.lookup("qom/object.h").add_types([
        Type("ObjectClass", False),
        Type("Object", False),
        Structure("TypeInfo",
            fields = [
                # These are required fields only
                Pointer(Type.lookup("const char")).gen_var("name"),
                Pointer(Type.lookup("const char")).gen_var("parent"),
                Pointer(Type.lookup("void")).gen_var("class_init")
            ]
        ),
        Type("Type", False),
        Type("TypeImpl", False),
        Function(name = "type_register_static",
            ret_type = Type.lookup("TypeImpl"),
            args = [
                Type.lookup("TypeInfo").gen_var("info", pointer = True)
            ]
        ),
        Function(name = "type_register",
            ret_type = Type.lookup("TypeImpl"),
            args = [
                Type.lookup("TypeInfo").gen_var("info", pointer = True)
            ]
        ),
        Function("object_get_typename"),
        Function("object_property_set_str"),
        Function("object_property_set_link"),
        Function("object_property_set_bool"),
        Function("object_property_set_int"),
        Function("object_class_by_name"),
        Function("object_class_dynamic_cast"),
        Function("object_class_is_abstract")
    ]).add_reference(osdep_fake_type)

    Header.lookup("qom/cpu.h").add_types([
        Type("CPUState", False),
        Type("CPUClass", False),
        Type("vaddr", False),
        Type("MMUAccessType", False),
        Type("CPUBreakpoint", False),
        Function("qemu_init_vcpu",
                 args = [
                     Type.lookup("CPUState").gen_var("cpu", pointer = True)
                 ]
        ),
        Function("cpu_exec_realizefn"),
        Function("cpu_reset"),
        Function("cpu_generic_init")
    ]).add_reference(osdep_fake_type)

    Header.lookup("qapi/error.h").add_types([
        Type("Error"),
        Function("error_propagate")
    ]).add_reference(osdep_fake_type)

    Header.lookup("disas/bfd.h").add_types([
        Type("disassemble_info", False)
    ]).add_reference(osdep_fake_type)


    Header.lookup("qemu/fprintf-fn.h").add_types([
        Type("fprintf_function", False)
    ]).add_reference(osdep_fake_type)

    if get_vp()["tlb_fill has SIZE argument"]:
        tlb_fill = Function("tlb_fill",
                args = [
                    Type.lookup("CPUState").gen_var("cs", pointer = True),
                    Type.lookup("target_ulong").gen_var("addr"),
                    Type.lookup("int").gen_var("size"),
                    Type.lookup("MMUAccessType").gen_var("access_type"),
                    Type.lookup("int").gen_var("mmu_idx"),
                    Type.lookup("uintptr_t").gen_var("retaddr")
                ],
                used_types = []
        )
    else:
        tlb_fill = Function("tlb_fill",
                args = [
                    Type.lookup("CPUState").gen_var("cs", pointer = True),
                    Type.lookup("target_ulong").gen_var("addr"),
                    Type.lookup("MMUAccessType").gen_var("access_type"),
                    Type.lookup("int").gen_var("mmu_idx"),
                    Type.lookup("uintptr_t").gen_var("retaddr")
                ],
                used_types = []
        )
    Header.lookup("exec/exec-all.h").add_types([
        Type("TranslationBlock", False),
        tlb_fill,
        Function("cpu_exec_init",
                 args = [
                     Type.lookup("CPUState").gen_var("cs", pointer = True),
                     Pointer(Pointer(Type.lookup("Error"))).gen_var("errp")
                 ]
        ),
        Function("gen_intermediate_code"),
        Function("cpu_restore_state"),
        Function("cpu_loop_exit"),
        Function("cpu_loop_exit_restore"),
        Function("tlb_set_page")
    ]).add_reference(osdep_fake_type)

    Header.lookup("exec/gen-icount.h").add_types([
        Function("gen_tb_start"),
        Function("gen_tb_end")
    ])

    Header.lookup("exec/address-spaces.h").add_types([
        Function("get_system_memory")
    ]).add_reference(osdep_fake_type)

    Header.lookup("exec/memory.h").add_types([
        Type("MemoryRegion", False),
        Function(name = "MemoryRegionOps_read",
            ret_type = Type.lookup("uint64_t"),
            args = [
                Type.lookup("void").gen_var("opaque", pointer = True),
                Type.lookup("hwaddr").gen_var("offset"),
                Type.lookup("unsigned").gen_var("size")
            ]
        ),
        Function(name = "MemoryRegionOps_write",
            ret_type = Type.lookup("void"),
            args = [
                Type.lookup("void").gen_var("opaque", pointer = True),
                Type.lookup("hwaddr").gen_var("offset"),
                Type.lookup("uint64_t").gen_var("value"),
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
        ),
        Function("memory_region_init"),
        Function("memory_region_init_alias"),
        Function("memory_region_init_ram"),
        Function("memory_region_add_subregion_overlap"),
        Function("memory_region_add_subregion")
    ]).add_reference(osdep_fake_type)

    Header.lookup("exec/gdbstub.h").add_types([
        Function(name = "gdb_get_reg8"),
        Function(name = "gdb_get_reg16"),
        Function(name = "gdb_get_reg32"),
        Function(name = "gdb_get_reg64")
    ]).add_reference(osdep_fake_type)

    Header.lookup("exec/ioport.h").add_types([
        Type("pio_addr_t", incomplete = False)
    ]).add_reference(osdep_fake_type)

    Header.lookup("hw/boards.h").add_types([
        Structure("MachineClass"),
        Structure("MachineState")
    ]).add_reference(osdep_fake_type)

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
        ),
        Function("sysbus_mmio_map"),
        Function("sysbus_connect_irq")
    ]).add_reference(osdep_fake_type)

    Header.lookup("hw/irq.h").add_types([
        Function(name = "qemu_irq_handler",
            ret_type = Type.lookup("void"),
            args = [
                Type.lookup("void").gen_var("opaque", pointer = True),
                Type.lookup("int").gen_var("n"),
                Type.lookup("int").gen_var("level")
            ]
        ),
        Function("qemu_irq_split")
    ]).add_reference(osdep_fake_type)

    Header.lookup("hw/qdev-core.h").add_types([
        Type("DeviceClass", False),
        Type("DeviceState", False),
        Type("Property", False),
        Function(name = "qdev_init_gpio_in",
            ret_type = Type.lookup("void"),
            args = [
                Type.lookup("DeviceState").gen_var("dev", pointer = True),
                Type.lookup("qemu_irq_handler").gen_var("handler"),
                Type.lookup("int").gen_var("n")
            ]
        ),
        Pointer(
            Function(
                name = "device_realize pointee",
                args = [
                    Type.lookup("DeviceState").gen_var("dev", pointer = True),
                    Pointer(Type.lookup("Error")).gen_var("errp",
                        pointer = True
                    )
                ]
            ),
            name = "DeviceRealize",
        ),
        Function(name = "qdev_create"),
        Function(name = "qdev_init_nofail"),
        Function(name = "qdev_get_child_bus"),
        Structure(name = "BusState"),
        Function(name = "qdev_get_gpio_in"),
        Function(name = "qdev_get_gpio_in_named"),
        Function(name = "qdev_connect_gpio_out"),
        Function(name = "qdev_connect_gpio_out_named")
    ]).add_reference(osdep_fake_type)

    Header.lookup("migration/vmstate.h").add_types([
        Type("VMStateDescription", False),
        Type("VMStateField", False),
        Function("vmstate_register_ram_global")
    ]).add_reference(osdep_fake_type)

    Header.lookup("qemu/module.h").add_reference(osdep_fake_type)

    Header.lookup("hw/pci/pci.h").add_types([
        Type("PCIDevice", False),
        Type("PCIDeviceClass", False),
        Function("pci_create_multifunction"),
        Type("PCIIOMMUFunc"),
    ]).add_reference(osdep_fake_type)

    Header.lookup("hw/pci/msi.h").add_types([
        Function(name = "msi_uninit"
            , ret_type = Type.lookup("void")
            , args = [
                Type.lookup("PCIDevice").gen_var("dev", pointer = True)
            ]
        )
    ]).add_reference(osdep_fake_type)

    Header.lookup("hw/pci/pci_bus.h").add_types([
        Type("PCIBus", incomplete = True)
    ]).add_references([
        Type.lookup("PCIIOMMUFunc"),
        osdep_fake_type
    ])
    Header.lookup("hw/pci/pci_host.h").add_reference(osdep_fake_type)

    Header.lookup("qemu/typedefs.h").add_types([
        # BlockBackend is defined in internal block_int.h. Its fields may not
        # be accessed outside internal code. Methods from block-backend.h must
        # be used instead.
        Structure("BlockBackend"),
        Structure("I2CBus") # the structure is defined in .c file
    ]).add_reference(osdep_fake_type)

    Header.lookup("qemu/bswap.h").add_types([
        Function("bswap64"),
        Function("bswap32"),
        Function("bswap16")
    ]).add_reference(osdep_fake_type)

    Header.lookup("hw/ide/internal.h").add_types([
        Structure("IDEDMA")
    ]).add_reference(osdep_fake_type)

    Header.lookup("hw/ide/ahci.h").add_references([
        Type.lookup("IDEDMA"),
        osdep_fake_type
    ])

    Header.lookup("hw/block/flash.h").add_references([
        Type.lookup("VMStateDescription"),
        osdep_fake_type
    ])

    Header.lookup("qemu/timer.h").add_types([
        Structure("QEMUTimer"),
        Function("timer_new_ns"),
        Function("timer_del"),
        Function("timer_free"),
        Type("QEMU_CLOCK_VIRTUAL") # It is enumeration entry...
    ]).add_references([
        osdep_fake_type
    ])

    Header.lookup("qemu/main-loop.h").add_types([
        Function("IOCanReadHandler",
            ret_type = Type.lookup("int"),
            args = [
                Pointer(Type.lookup("void")).gen_var("opaque")
            ]
        ),
        Function("IOReadHandler",
            args = [
                Pointer(Type.lookup("void")).gen_var("opaque"),
                Pointer(Type.lookup("uint8_t"), const = True).gen_var("buf"),
                Type.lookup("int").gen_var("size")
            ]
        )
    ]).add_references([
        osdep_fake_type
    ])

    if get_vp()["v2.8 chardev"]:
        chardev_types = [
            Function("qemu_chr_fe_set_handlers"),
            Structure("CharBackend")
        ]
    else:
        chardev_types = [
            Function("qemu_chr_add_handlers"),
            Structure("CharDriverState")
        ]

    Header.lookup(get_vp("header with IOEventHandler")).add_types([
        Function("IOEventHandler",
            args = [
                Pointer(Type.lookup("void")).gen_var("opaque"),
                Type.lookup("int").gen_var("event")
            ]
        )
    ] + chardev_types).add_references([
        osdep_fake_type
    ])

    Header.lookup("sysemu/block-backend.h").add_types([
        Structure("BlockDevOps"),
    ]).add_references([
        osdep_fake_type
    ])

    Header.lookup("hw/isa/isa.h").add_types([
        Type("IsaDmaTransferHandler")
    ])

    if get_vp()["include/hw/isa/i8257.h have IsaDmaTransferHandler reference"]:
        Header.lookup(get_vp()["i8257.h path"]).add_references([
            Type.lookup("IsaDmaTransferHandler"),
            Type.lookup("MemoryRegion")
        ])

    Header.lookup("net/net.h").add_types([
        Type("qemu_macaddr_default_if_unset"),
        Type("qemu_format_nic_info_str"),
        Type("qemu_new_nic"),
        Type("qemu_del_nic"),
        Type("qemu_get_queue"),
        Structure("NICConf"),
        Type("NICState"),
        Type("NetClientState"),
        Function("NetCanReceive",
            ret_type = Type.lookup("int"),
            args = [
                Pointer(Type.lookup("NetClientState")).gen_var("nc")
            ]
        ),
        Function("NetReceive",
            ret_type = Type.lookup("ssize_t"),
            args = [
                Pointer(Type.lookup("NetClientState")).gen_var("nc"),
                Pointer(Type.lookup("const uint8_t")).gen_var("buf"),
                Type.lookup("size_t").gen_var("size")
            ]
        ),
        Function("LinkStatusChanged",
            args = [
                Pointer(Type.lookup("NetClientState")).gen_var("nc")
            ]
        ),
        Function("NetCleanup",
            args = [
                Pointer(Type.lookup("NetClientState")).gen_var("nc")
            ]
        ),
        Structure("NetClientInfo",
            fields = [
                # "type" field type is enum NetClientDriver, but enum is not
                # supported by model
                Type.lookup("int").gen_var("type"),
                Type.lookup("size_t").gen_var("size"),
                Type.lookup("NetReceive").gen_var("receive"),
                Type.lookup("NetCanReceive").gen_var("can_receive"),
                Type.lookup("NetCleanup").gen_var("cleanup"),
                Type.lookup("LinkStatusChanged").gen_var("link_status_changed")
                # There are other fields but they are not needed.
            ]
        ),
        Macro("NET_CLIENT_DRIVER_NIC") # This is an enum item actually. It
        # is defined in auto generated "qapi-types.h" which is not presented in
        # registry but is included by "net.h" indirectly.
    ]).add_references([
        osdep_fake_type
    ])

    Header.lookup("exec/helper-proto.h").add_type(
        Macro("HELPER_PROTO_H")
    )

    Header.lookup("disas/bfd.h").add_types([
        Type("bfd_vma", False)
    ])
    Header.lookup("disas/bfd.h").add_types([
        Type("bfd_byte", False)
    ])
    Header.lookup("disas/bfd.h").add_types([
        Type("const bfd_tyte", False)
    ])
    Header.lookup("disas/bfd.h").add_types([
        Function("bfd_getl64",
            ret_type = Type.lookup("bfd_vma"),
            args = [
                Pointer(Type.lookup("const bfd_tyte")).gen_var("addr", pointer = True)
            ]
        )
    ])
    Header.lookup("disas/bfd.h").add_types([
        Function("bfd_getl32",
            ret_type = Type.lookup("bfd_vma"),
            args = [
                Pointer(Type.lookup("const bfd_tyte")).gen_var("addr", pointer = True)
            ]
        )
    ])
    Header.lookup("disas/bfd.h").add_types([
        Function("bfd_getb32",
            ret_type = Type.lookup("bfd_vma"),
            args = [
                Pointer(Type.lookup("const bfd_tyte")).gen_var("addr", pointer = True)
            ]
        )
    ])
    Header.lookup("disas/bfd.h").add_types([
        Function("bfd_getl16",
            ret_type = Type.lookup("bfd_vma"),
            args = [
                Pointer(Type.lookup("const bfd_tyte")).gen_var("addr", pointer = True)
            ]
        )
    ])
    Header.lookup("disas/bfd.h").add_types([
        Function("bfd_getb16",
            ret_type = Type.lookup("bfd_vma"),
            args = [
                Pointer(Type.lookup("const bfd_tyte")).gen_var("addr", pointer = True)
            ]
        )
    ])


    Header.lookup("disas/disas.h").add_types([
        Function("lookup_symbol")
    ])
    Header.lookup("qemu/log.h").add_types([
        Function("qemu_loglevel_mask"),
        Function("qemu_log_in_addr_range"),
        Function("qemu_log_lock"),
        Function("qemu_log_unlock"),
        Function("qemu_log")
    ])
    Header.lookup("exec/log.h").add_types([
        Function("log_target_disas")
    ])

def define_qemu_2_6_5_types():
    add_base_types()
    define_only_qemu_2_6_0_types()

def define_qemu_2_6_0_types():
    add_base_types()
    # The paths of the headers are presented relative root directory.
    Header("hw/ide/internal.h")
    Header("hw/ide/ahci.h")
    define_only_qemu_2_6_0_types()

def define_msi_init_2_6_5():
    Header.lookup("hw/pci/msi.h").add_type(
        Function(name = "msi_init"
            , ret_type = Type.lookup("int")
            , args = [
                Type.lookup("PCIDevice").gen_var("dev", pointer = True)
                , Type.lookup("uint8_t").gen_var("offset")
                , Type.lookup("unsigned int").gen_var("nr_vectors")
                , Type.lookup("bool").gen_var("msi64bit")
                , Type.lookup("bool").gen_var("msi_per_vector_mask")
                , Pointer(Type.lookup("Error")).gen_var("errp", pointer = True)
            ]
        )
    )

def define_msi_init_2_6_0():
    Header.lookup("hw/pci/msi.h").add_type(
        Function(name = "msi_init"
            , ret_type = Type.lookup("int")
            , args = [
                Type.lookup("PCIDevice").gen_var("dev", pointer = True)
                , Type.lookup("uint8_t").gen_var("offset")
                , Type.lookup("unsigned int").gen_var("nr_vectors")
                , Type.lookup("bool").gen_var("msi64bit")
                , Type.lookup("bool").gen_var("msi_per_vector_mask")
            ]
        )
    )

def machine_register_2_5(mach):
    # machine class definition function
    mach.class_init = Function(
        name = "machine_%s_class_init" % mach.qtn.for_id_name,
        static = True,
        ret_type = Type.lookup("void"),
        args = [
            Type.lookup("ObjectClass").gen_var("oc", pointer = True),
            Type.lookup("void").gen_var("opaque", pointer = True)
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
            Type.lookup("MachineClass"),
            Type.lookup("MACHINE_CLASS"),
            mach.instance_init
        ]
    )
    mach.source.add_type(mach.class_init)

    # machine type definition structure
    type_machine_macro = Type.lookup("TYPE_MACHINE")
    type_machine_suf_macro = Type.lookup("TYPE_MACHINE_SUFFIX")

    mach.type_info = Type.lookup("TypeInfo").gen_var(
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
""".format(
    type_info = mach.type_info.name
        ),
        static = True,
        used_types = [Type.lookup("type_register")],
        used_globals = [mach.type_info]
    )
    mach.source.add_type(mach.type_reg_func)

    # Main machine registration macro
    def_type = get_vp()["machine initialization function register type name"]
    machine_init_def = Type.lookup(def_type).gen_var()
    machine_init_def_args = Initializer(
        code = { "function": mach.type_reg_func }
    )
    mach.source.add_usage(machine_init_def.gen_usage(machine_init_def_args))

def machine_register_2_6(mach):
    # machine class definition function
    mach.class_init = Function(
        name = "machine_%s_class_init" % mach.qtn.for_id_name,
        static = True,
        ret_type = Type.lookup("void"),
        args = [
            Type.lookup("ObjectClass").gen_var("oc", pointer = True),
            Type.lookup("void").gen_var("opaque", pointer = True)
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
            Type.lookup("MachineClass"),
            Type.lookup("MACHINE_CLASS"),
            mach.instance_init
        ]
    )
    mach.source.add_type(mach.class_init)

    # machine type definition structure
    type_machine_macro = Type.lookup("TYPE_MACHINE")
    type_machine_type_name_macro = Type.lookup("MACHINE_TYPE_NAME")

    mach.type_info = Type.lookup("TypeInfo").gen_var(
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
    machine_init_def = Type.lookup("type_init").gen_var()
    machine_init_def_args = Initializer({ "function": mach.type_reg_func })
    mach.source.add_usage(machine_init_def.gen_usage(machine_init_def_args))

qemu_heuristic_db = {
    u'fcf5ef2ab52c621a4617ebbef36bf43b4003f4c0' : [
        # This commit moves target-* CPU file into a target/ folder
        # So target-xxx/ becomes target/xxx/ instead.
        QEMUVersionParameterDescription("target folder",
        new_value = 'target' + sep,
        old_value = 'target-'
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
        QEMUVersionParameterDescription("i8257.h path",
            new_value = "hw/dma/i8257.h",
            old_value = "hw/isa/i8257.h"
        )
    ],
    u'1c2adb958fc07e5b3e81ed21b801c04a15f41f4f':
    [
        QEMUVersionParameterDescription("Init cpu_env in arch",
            old_value = True,
            new_value = False
        )
    ],
    u'9c489ea6bed134fecfd556b439c68bba48fbe102':
    [
        QEMUVersionParameterDescription("gen_intermediate_code arg1 is generic",
            old_value = False,
            new_value = True
        )
    ],
    u'0dacec874fa3b3fd34b0d0670fa257efdcbbebd0':
    [
        QEMUVersionParameterDescription("CPU_RESOLVING_TYPE",
            old_value = False,
            new_value = True
        )
    ],
    u'3f71e724e283233753f1b5b3d6a30948d3084636':
    [
        QEMUVersionParameterDescription("Create cpu_init",
            old_value = True,
            new_value = False
        )
    ],
    u'98670d47cd8d63a529ff230fd39ddaa186156f8c':
    [
        QEMUVersionParameterDescription("tlb_fill has SIZE argument",
            old_value = False,
            new_value = True
        )
    ],
    u'1d48474d8e9eff9d08ad43477043d95789b96a40':
    [
        QEMUVersionParameterDescription("target_disas has FLAGS argument",
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

