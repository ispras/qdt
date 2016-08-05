from source import \
    Header, \
    Type, \
    Function, \
    Macro, \
    Structure

from pci_ids import \
    re_pci_vendor, \
    re_pci_class, \
    re_pci_device, \
    pci_id_db, \
    PCIVendorId, \
    PCIClassId, \
    PCIDeviceId

from sysbusdevice import \
    SysBusDeviceStateStruct, \
    SysBusDeviceType

from pcie import \
    PCIEDeviceStateStruct, \
    PCIEDeviceType
    
from qom import \
    QemuTypeName, \
    QOMType

from machine import \
    MachineType

from machine_description import \
    Node, \
    MachineNode, \
    BusNode, \
    I2CBusNode, \
    SystemBusNode, \
    SystemBusDeviceNode, \
    PCIExpressBusNode, \
    PCIExpressDeviceNode, \
    ISABusNode, \
    IDEBusNode, \
    DeviceNode, \
    IRQLine, \
    IRQHub, \
    QOMPropertyType, \
    QOMPropertyTypeLink, \
    QOMPropertyTypeString, \
    QOMPropertyTypeBoolean, \
    QOMPropertyTypeInteger, \
    QOMPropertyValue, \
    MemoryNode, \
    MemoryAliasNode, \
    MemoryRAMNode, \
    MemoryROMNode

from project import \
    QProject

from device_description import \
    SysBusDeviceDescription, \
    PCIExpressDeviceDescription

from version import \
    initialize as qemu_version_initialize, \
    get_vp, \
    get_vs

from machine_editing import \
    MachineOperation, \
        MachineDeviceOperation, \
            MachineDeviceSetAttributeOperation, \
            MachineIOMappingOperation, \
                MOp_DelIOMapping, \
                MOp_AddIOMapping, \
                MOp_SetIOMapping, \
            MOp_SetDevParentBus, \
            MOp_SetDevQOMType, \
            MachineDevicePropertyOperation, \
                MOp_DelDevProp, \
                MOp_AddDevProp, \
                MOp_SetDevProp, \
    MachineHistoryTracker

import os

def initialize(qemu_src):
    VERSION_path = os.path.join(qemu_src, 'VERSION')

    if not os.path.isfile(VERSION_path):
        raise Exception("{} does not exists\n".format(VERSION_path))

    VERSION_f = open(VERSION_path)
    qemu_version = VERSION_f.readline().rstrip("\n")
    VERSION_f.close()

    print("Qemu version is {}".format(qemu_version))

    include_path = os.path.join(qemu_src, 'include')
    
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
        Function("object_property_set_str"),
        Function("object_property_set_link"),
        Function("object_property_set_bool"),
        Function("object_property_set_int"),
        Macro("OBJECT")
        ])

    Header.lookup("exec/memory.h").add_types([
        Type("MemoryRegion", False),
        Function(name = "MemoryRegionOps_read",
            ret_type = Type.lookup("uint64_t"),
            args = [
                Type.lookup("void").gen_var("opaque", pointer = True),
                Type.lookup("hwaddr").gen_var("addr"),
                Type.lookup("unsigned").gen_var("size")
            ]
        ),
        Function(name = "MemoryRegionOps_write",
            ret_type = Type.lookup("void"),
            args = [
                Type.lookup("void").gen_var("opaque", pointer = True),
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
        ),
        Function("memory_region_init"),
        Function("memory_region_init_alias"),
        Function("memory_region_init_ram"),
        Function("memory_region_add_subregion_overlap"),
        Function("memory_region_add_subregion")
        ])

    Header.lookup("exec/ioport.h").add_types([
        Type("pio_addr_t", incomplete=False)
        ])

    Header.lookup("hw/boards.h").add_types([
        Macro("MACHINE_CLASS"),
        Structure("MachineClass"),
        Structure("MachineState")
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
        ),
        Function("sysbus_mmio_map"),
        Macro("SYS_BUS_DEVICE"),
        Function("sysbus_connect_irq")
        ])

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

    Header.lookup("qapi/error.h").add_types([
        Type("Error*", False)
        ])

    Header.lookup("migration/vmstate.h").add_types([
        Type("VMStateDescription", False),
        Type("VMStateField", False),
        Function("vmstate_register_ram_global")
        ])

    Header.lookup("qemu/module.h").add_types([
        Macro(name = "type_init", 
            args = [
                "function"
            ]
        ),
        Macro(name = "machine_init", args = ["function"])
        ])

    Header.lookup("hw/pci/pci.h").add_types([
        Type("PCIDevice", False),
        Type("PCIDeviceClass", False),
        Function("pci_create_multifunction"),
        Macro("PCI_DEVFN")
        ])

    Header.lookup("hw/pci/msi.h").add_types([
        Function(name="msi_init"
            , ret_type = Type.lookup("int")
            , args = [
                Type.lookup("PCIDevice").gen_var("dev", pointer = True)
                , Type.lookup("uint8_t").gen_var("offset")
                , Type.lookup("unsigned int").gen_var("nr_vectors")
                , Type.lookup("bool").gen_var("msi64bit")
                , Type.lookup("bool").gen_var("msi_per_vector_mask")
            ]
        )
        , Function(name="msi_uninit"
            , ret_type = Type.lookup("void")
            , args = [
                Type.lookup("PCIDevice").gen_var("dev", pointer = True)
            ]
        )
        ])

    Header.lookup("hw/pci/pci_bus.h").add_types([
        Type("PCIBus", incomplete = True)
        ])

    Header.lookup("hw/pci/pci_host.h").add_types([
        Macro(name = "PCI_HOST_BRIDGE")
        ])

    Header.lookup("qemu/typedefs.h").add_types([
        Structure("I2CBus") # the structure is defined in .c file
        ])

    # Search for PCI Ids
    for t in Type.reg.values():
        if type(t) == Macro:
            mi = re_pci_vendor.match(t.name)
            if mi:
                PCIVendorId(mi.group(1), t.text)
                continue

            mi = re_pci_class.match(t.name)
            if mi:
                # print 'PCI class %s' % mi.group(1)
                PCIClassId(mi.group(1), t.text)
                continue

    # All PCI vendors must be defined before any device.
    for t in Type.reg.values():
        if type(t) == Macro:
            mi = re_pci_device.match(t.name)
            if mi:
                for v in pci_id_db.vendors.values():
                    mi = v.device_pattern.match(t.name)
                    if mi:
                        PCIDeviceId(v.name, mi.group(1), t.text)
                        break;
                continue

    qemu_version_initialize(qemu_version)
