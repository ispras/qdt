from source import \
    Type, \
    Function, \
    Macro, \
    Structure

def add_types(stc):
    stc.header_lookup("exec/hwaddr.h").add_types([
        Type("hwaddr", False)
        ])

    stc.header_lookup("qom/object.h").add_types([
        Type("ObjectClass", False),
        Type("Object",  False),
        Type("TypeInfo",  False),
        Type("Type",  False),
        Type("TypeImpl",  False),
        Function(name = "type_register_static",
            ret_type = stc.type_lookup("TypeImpl"),
            args = [
                stc.type_lookup("TypeInfo").gen_var("info", pointer = True)
            ]
        ),
        Function(name = "type_register",
            ret_type = stc.type_lookup("TypeImpl"),
            args = [
                stc.type_lookup("TypeInfo").gen_var("info", pointer = True)
            ]
        ),
        Function("object_property_set_str"),
        Function("object_property_set_link"),
        Function("object_property_set_bool"),
        Function("object_property_set_int"),
        Macro("OBJECT")
        ])

    stc.header_lookup("exec/memory.h").add_types([
        Type("MemoryRegion", False),
        Function(name = "MemoryRegionOps_read",
            ret_type = stc.type_lookup("uint64_t"),
            args = [
                stc.type_lookup("void").gen_var("opaque", pointer = True),
                stc.type_lookup("hwaddr").gen_var("addr"),
                stc.type_lookup("unsigned").gen_var("size")
            ]
        ),
        Function(name = "MemoryRegionOps_write",
            ret_type = stc.type_lookup("void"),
            args = [
                stc.type_lookup("void").gen_var("opaque", pointer = True),
                stc.type_lookup("hwaddr").gen_var("addr"),
                stc.type_lookup("uint64_t").gen_var("data"),
                stc.type_lookup("unsigned").gen_var("size")
            ]
        ),
        Structure("MemoryRegionOps",
            [   stc.type_lookup("MemoryRegionOps_read").gen_var("read"),
                stc.type_lookup("MemoryRegionOps_write").gen_var("write")
            ]
        ),
        Function(name = "memory_region_init_io",
            args = [
                stc.type_lookup("MemoryRegion").gen_var("mr", pointer = True),
                # struct
                stc.type_lookup("Object").gen_var("owner", pointer = True),
                # const
                stc.type_lookup("MemoryRegionOps").gen_var("ops", pointer = True),
                stc.type_lookup("void").gen_var("opaque", pointer = True),
                stc.type_lookup("const char").gen_var("name", pointer = True),
                stc.type_lookup("uint64_t").gen_var("size")
            ]
        ),
        Function("memory_region_init"),
        Function("memory_region_init_alias"),
        Function("memory_region_init_ram"),
        Function("memory_region_add_subregion_overlap"),
        Function("memory_region_add_subregion")
        ])

    stc.header_lookup("exec/ioport.h").add_types([
        Type("pio_addr_t", incomplete=False)
        ])

    stc.header_lookup("hw/boards.h").add_types([
        Macro("MACHINE_CLASS"),
        Structure("MachineClass"),
        Structure("MachineState")
        ])

    stc.header_lookup("hw/sysbus.h").add_types([
        Type("SysBusDevice", False),
        Type("qemu_irq", False),
        Function(name = "sysbus_init_mmio",
            ret_type = stc.type_lookup("void"),
            args = [
                stc.type_lookup("SysBusDevice").gen_var("dev", pointer = True),
                stc.type_lookup("MemoryRegion").gen_var("memory", pointer = True)
            ]
        ),
        Function(name = "sysbus_init_irq",
            ret_type = stc.type_lookup("void"),
            args = [
                stc.type_lookup("SysBusDevice").gen_var("dev", pointer = True),
                stc.type_lookup("qemu_irq").gen_var("p", pointer = True)
            ]
        ),
        Function(name = "sysbus_add_io",
            ret_type = stc.type_lookup("void"),
            args = [
                stc.type_lookup("SysBusDevice").gen_var("dev", pointer = True),
                stc.type_lookup("hwaddr").gen_var("addr"),
                stc.type_lookup("MemoryRegion").gen_var("mem", pointer = True)
            ]
        ),
        Function(name = "sysbus_init_ioports",
            ret_type = stc.type_lookup("void"),
            args = [
                stc.type_lookup("SysBusDevice").gen_var("dev", pointer = True),
                stc.type_lookup("pio_addr_t").gen_var("dev"),
                stc.type_lookup("pio_addr_t").gen_var("dev")
            ]
        ),
        Function("sysbus_mmio_map"),
        Macro("SYS_BUS_DEVICE"),
        Function("sysbus_connect_irq")
        ])

    stc.header_lookup("hw/irq.h").add_types([
        Function(name = "qemu_irq_handler",
            ret_type = stc.type_lookup("void"),
            args = [
                stc.type_lookup("void").gen_var("opaque", pointer = True),
                stc.type_lookup("int").gen_var("n"),
                stc.type_lookup("int").gen_var("level")
            ]
        ),
        Function("qemu_irq_split")
    ])

    stc.header_lookup("hw/qdev-core.h").add_types([
        Type("DeviceClass", False),
        Type("DeviceState", False),
        Macro(name = "DEVICE", args = ["obj"]),
        Type("Property", False),
        Function(name = "qdev_init_gpio_in",
            ret_type = stc.type_lookup("void"),
            args = [
                stc.type_lookup("DeviceState").gen_var("dev", pointer = True),
                stc.type_lookup("qemu_irq_handler").gen_var("handler"),
                stc.type_lookup("int").gen_var("n")
            ]
        ),
        Function(name = "qdev_create"),
        Function(name = "qdev_init_nofail"),
        Function(name = "qdev_get_child_bus"),
        Macro(name = "BUS"),
        Structure(name = "BusState"),
        Function(name = "qdev_get_gpio_in"),
        Function(name = "qdev_connect_gpio_out"),
        Function(name = "qdev_connect_gpio_out_named")
        ])

    stc.header_lookup("qapi/error.h").add_types([
        Type("Error*", False)
        ])

    stc.header_lookup("migration/vmstate.h").add_types([
        Type("VMStateDescription", False),
        Type("VMStateField", False),
        Function("vmstate_register_ram_global")
        ])

    stc.header_lookup("qemu/module.h").add_types([
        Macro(name = "type_init",
            args = [
                "function"
            ]
        ),
        Macro(name = "machine_init", args = ["function"])
        ])

    stc.header_lookup("hw/pci/pci.h").add_types([
        Type("PCIDevice", False),
        Type("PCIDeviceClass", False),
        Function("pci_create_multifunction"),
        Macro("PCI_DEVFN")
        ])

    stc.header_lookup("hw/pci/msi.h").add_types([
        Function(name="msi_init"
            , ret_type = stc.type_lookup("int")
            , args = [
                stc.type_lookup("PCIDevice").gen_var("dev", pointer = True)
                , stc.type_lookup("uint8_t").gen_var("offset")
                , stc.type_lookup("unsigned int").gen_var("nr_vectors")
                , stc.type_lookup("bool").gen_var("msi64bit")
                , stc.type_lookup("bool").gen_var("msi_per_vector_mask")
            ]
        )
        , Function(name="msi_uninit"
            , ret_type = stc.type_lookup("void")
            , args = [
                stc.type_lookup("PCIDevice").gen_var("dev", pointer = True)
            ]
        )
        ])
