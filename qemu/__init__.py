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

import os

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
        )
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
        )
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
        ),
        Macro(name = "machine_init", args = ["function"])
        ])

    Header.lookup("hw/pci/pci.h").add_types([
        Type("PCIDevice", False),
        Type("PCIDeviceClass", False)
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
