__all__ = [
    "Q35MachineNode_2_5_0"
  , "Q35MachineNode_2_6_0"
  , "Q35Project_2_5_0"
  , "Q35Project_2_6_0"
]

from qemu import (
    QProject,
    SysBusDeviceDescription,
    MachineNode,
    MemoryNode,
    MemoryRAMNode,
    MemoryROMNode,
    IRQLine,
    IRQHub,
    DeviceNode,
    PCIExpressDeviceNode,
    SystemBusDeviceNode,
    PCIExpressBusNode,
    ISABusNode,
    IDEBusNode,
    I2CBusNode,
    QOMPropertyValue,
    QOMPropertyTypeInteger,
    QOMPropertyTypeLink,
    QOMPropertyTypeBoolean,
    QOMPropertyTypeString
)
from six.moves import range as xrange

def Q35MachineNode_2_5_0():
    self = MachineNode("q35_test", "i386")

    cpu = DeviceNode(
        qom_type = "qemu64-x86_64-cpu"
        )
    cpu.properties.extend([
        QOMPropertyValue(QOMPropertyTypeInteger, "apic-id", 0)
        ])
    self.add_node(cpu)

    # set CPUID with smbios_set_cpuid(cpu->env.cpuid_version, cpu->env.features[FEAT_1_EDX]);
    # call pc_acpi_init("q35-acpi-dsdt.aml");

    # get memory size from machine->ram_size
    memory_size = 1024 * 1024 * 1024

    ram_mem = MemoryRAMNode("ram", memory_size)

    pci_mem = MemoryNode("pci", "UINT64_MAX")

    rom_mem = MemoryROMNode("pc.rom", "PC_ROM_SIZE")
    pci_mem.add_child(rom_mem, "PC_ROM_MIN_VGA", True, 1)

    # assuming BIOS image is 128 KB, get it from drive_get(IF_PFLASH, 0, 0)
    # User should provide it using -pflash option
    isa_bios_size = 128 * 1024
    isa_bios = MemoryROMNode("isa-bios", isa_bios_size)
    pci_mem.add_child(isa_bios, 0x100000 - isa_bios_size, True, 1)

    bios_flash = SystemBusDeviceNode(
        qom_type = "TYPE_CFI_PFLASH01",
        mmio = [0x100000000]
        )
    bios_flash.properties.extend([
        # drive is block device with BIOS image
        QOMPropertyValue(QOMPropertyTypeLink, "drive", None),
        # num-blocks is size of BIOS image divided by sector-length
        QOMPropertyValue(QOMPropertyTypeInteger, "num-blocks", isa_bios_size >> 12),

        QOMPropertyValue(QOMPropertyTypeInteger, "sector-length", 1 << 12),
        QOMPropertyValue(QOMPropertyTypeInteger, "width", 1),
        QOMPropertyValue(QOMPropertyTypeBoolean, "big-endian", False),
        QOMPropertyValue(QOMPropertyTypeInteger, "id0", 0),
        QOMPropertyValue(QOMPropertyTypeInteger, "id1", 0),
        QOMPropertyValue(QOMPropertyTypeInteger, "id2", 0),
        QOMPropertyValue(QOMPropertyTypeInteger, "id3", 0),
        QOMPropertyValue(QOMPropertyTypeString, "name", "system.flash0")
        ])
    self.add_node(bios_flash)

    # smbios_set_defaults("QEMU", "Standard PC (Q35 + ICH9, 2009)", MACHINE_GET_CLASS(machine)->name, false, true, SMBIOS_ENTRY_POINT_21)
    # Copy data from BIOS flash to ISA BIOS ROM

    pci_host = SystemBusDeviceNode(
        qom_type = "TYPE_Q35_HOST_DEVICE"
        )
    self.add_node(pci_host)

    pci_host.properties.extend([
        QOMPropertyValue(QOMPropertyTypeInteger, "PCI_HOST_BELOW_4G_MEM_SIZE", memory_size),
        QOMPropertyValue(QOMPropertyTypeInteger, "PCI_HOST_ABOVE_4G_MEM_SIZE", 0),
        QOMPropertyValue(QOMPropertyTypeLink, "MCH_HOST_PROP_RAM_MEM", ram_mem),
        QOMPropertyValue(QOMPropertyTypeLink, "MCH_HOST_PROP_PCI_MEM", pci_mem)
        ])

    pci_bus = PCIExpressBusNode(
        host_bridge = pci_host
        )

    bridge_pci2lpc = PCIExpressDeviceNode(
        qom_type = "TYPE_ICH9_LPC_DEVICE",
        pci_express_bus = pci_bus,
        slot = "ICH9_LPC_DEV",
        function = "ICH9_LPC_FUNC",
        multifunction = True
        )

    isa_bus = ISABusNode(
        bus_controller = bridge_pci2lpc
        )
    self.isa_bus = isa_bus

    i8259_master = DeviceNode(
        qom_type = "isa-i8259",
        parent = isa_bus
        )
    i8259_master.properties.extend([
        QOMPropertyValue(QOMPropertyTypeInteger, "iobase", 0x20),
        QOMPropertyValue(QOMPropertyTypeInteger, "elcr_addr", 0x4d0),
        QOMPropertyValue(QOMPropertyTypeInteger, "elcr_mask", 0xf8),
        QOMPropertyValue(QOMPropertyTypeBoolean, "master", True)
        ])

    i8259_slave = DeviceNode(
        qom_type = "isa-i8259",
        parent = isa_bus
        )
    i8259_slave.properties.extend([
        QOMPropertyValue(QOMPropertyTypeInteger, "iobase", 0xa0),
        QOMPropertyValue(QOMPropertyTypeInteger, "elcr_addr", 0x4d1),
        QOMPropertyValue(QOMPropertyTypeInteger, "elcr_mask", 0xde),
        QOMPropertyValue(QOMPropertyTypeBoolean, "master", False)
        ])

    # connect master 0-th out IRQ to CPU: pc_allocate_cpu_irq
    IRQLine(i8259_slave, i8259_master, 0, 2, None)

    ioapic = SystemBusDeviceNode(
        qom_type = "ioapic",
        mmio = [
                "IO_APIC_DEFAULT_ADDRESS"
            ]
        )

    hpet = SystemBusDeviceNode(
        qom_type = "TYPE_HPET",
        mmio = [
            "HPET_BASE"
            ]
        )
    hpet.properties.append(QOMPropertyValue(QOMPropertyTypeInteger, "HPET_INTCAP", 0xff0104))

    portF0 = SystemBusDeviceNode(
        qom_type = "TYPE_IO_PORT_F0",
        pmio = [0xF0]
        )

    for i in xrange(0, 24):
        dsts = [(ioapic, i, None)]
        if i == 2:
            pass
        elif i < 8:
            dsts.append((i8259_master, i, None))
        elif i < 16:
            dsts.append((i8259_slave, i - 8, None))

        srcs = [(bridge_pci2lpc, i + 16, None)]
        if i < 16:
            srcs.append((bridge_pci2lpc, i, None))

        if i == 13:
            srcs.append((portF0, 0, "SYSBUS_DEVICE_GPIO_IRQ"))

        srcs.append((hpet, i, "SYSBUS_DEVICE_GPIO_IRQ"))

        IRQHub(srcs, dsts)

    port80 = SystemBusDeviceNode(
        qom_type = "TYPE_IO_PORT_80",
        pmio = [0x80]
        )
    self.add_node(port80)

    rtc = DeviceNode(
        qom_type = "TYPE_MC146818_RTC",
        parent = isa_bus
        )
    rtc.properties.append(QOMPropertyValue(QOMPropertyTypeInteger, "base_year", 2000))
    # qemu_register_boot_set(pc_boot_set, rtc);

    IRQLine(rtc, hpet, 0, "HPET_LEGACY_RTC_INT")

    pit = DeviceNode(
        qom_type = "TYPE_I8254",
        parent = isa_bus
        )
    pit.properties.append(QOMPropertyValue(QOMPropertyTypeInteger, "iobase", 0x40))

    IRQLine(pit, hpet, 0, "HPET_LEGACY_PIT_INT")
    IRQLine(hpet, pit, 0, 0)

    speaker = DeviceNode(
        qom_type = "TYPE_PC_SPEAKER",
        parent = isa_bus
        )
    speaker.properties.extend([
        QOMPropertyValue(QOMPropertyTypeInteger, "iobase", 0x61),
        QOMPropertyValue(QOMPropertyTypeLink, "pit", pit) # the device uses opaque pointer instead of link
        ])

    serial = DeviceNode(
        qom_type = "TYPE_ISA_SERIAL",
        parent = isa_bus
        )
    serial.properties.extend([
        QOMPropertyValue(QOMPropertyTypeInteger, "index", 0),
        QOMPropertyValue(QOMPropertyTypeString, "chardev", "serial0")
        ])

    parallel = DeviceNode(
        qom_type = "isa-parallel",
        parent = isa_bus
        )
    parallel.properties.extend([
        QOMPropertyValue(QOMPropertyTypeInteger, "index", 0),
        QOMPropertyValue(QOMPropertyTypeString, "chardev", "parallel0")
        ])

    kbd_and_mouse = DeviceNode(
        qom_type = "i8042",
        parent = isa_bus
        )

    vmport = DeviceNode(
        qom_type = "TYPE_VMPORT",
        parent = isa_bus
        )

    vmmouse = DeviceNode(
        qom_type = "vmmouse",
        parent = isa_bus
        )
    vmmouse.properties.extend([
        QOMPropertyValue(QOMPropertyTypeLink, "ps2_mouse", kbd_and_mouse),
        QOMPropertyValue(QOMPropertyTypeLink, "vmport", vmport)
        ])

    port92 = DeviceNode(
        qom_type = "port92",
        parent = isa_bus
        )

    a20_line = SystemBusDeviceNode(
        qom_type = "TYPE_A20_LINE"
        )
    a20_line.properties.extend([
        QOMPropertyValue(QOMPropertyTypeLink, "cpu", cpu)
        ])
    IRQLine(kbd_and_mouse, a20_line, 0, 0)
    IRQLine(port92, a20_line, 0, 0)

    # for 2.5.0 call DMA_init(0);

    achi = PCIExpressDeviceNode(
        qom_type = "TYPE_ICH9_AHCI",
        pci_express_bus = pci_bus,
        slot = "ICH9_SATA1_DEV",
        function = "ICH9_SATA1_FUNC",
        multifunction = True
        )

    ide_0 = IDEBusNode(achi)
    ide_1 = IDEBusNode(achi)

    # create drives using:

    # DriveInfo *hd[MAX_SATA_PORTS];
    # ide_drive_get(hd, ICH_AHCI(ahci)->ahci.ports);
    # ahci_ide_create_devs(ahci, hd);

    ehci = PCIExpressDeviceNode(
        qom_type = "ich9-usb-ehci1",
        pci_express_bus = pci_bus,
        slot = 0x1d,
        function = 7,
        multifunction = True
        )

    uhci0 = PCIExpressDeviceNode(
        qom_type = "ich9-usb-uhci4",
        pci_express_bus = pci_bus,
        slot = 0x1d,
        function = 0,
        multifunction = True
        )

    uhci1 = PCIExpressDeviceNode(
        qom_type = "ich9-usb-uhci5",
        pci_express_bus = pci_bus,
        slot = 0x1d,
        function = 1,
        multifunction = True
        )

    uhci2 = PCIExpressDeviceNode(
        qom_type = "ich9-usb-uhci6",
        pci_express_bus = pci_bus,
        slot = 0x1d,
        function = 2,
        multifunction = True
        )

    i2c_bridge = PCIExpressDeviceNode(
        qom_type = "TYPE_ICH9_SMB_DEVICE",
        pci_express_bus = pci_bus,
        slot = "ICH9_SMB_DEV",
        function = "ICH9_SMB_FUNC",
        multifunction = True)

    i2c_bus = I2CBusNode(bus_controller = i2c_bridge)

    for i in xrange(0, 8):
        DeviceNode(
            qom_type = "smbus-eeprom",
            parent = i2c_bus).properties.extend([
                QOMPropertyValue(QOMPropertyTypeInteger, "address", 0x50 + i)
                ])

    # pc_cmos_init !!!

    # call pc_vga_init(NULL, pci_bus) and pc_nic_init(NULL, pci_bus);
    return self

def Q35MachineNode_2_6_0():
    self = Q35MachineNode_2_5_0()
    
    isa_dma_1 = DeviceNode(
        qom_type = "TYPE_I8257",
        parent = self.isa_bus
        )
    isa_dma_1.properties.extend([
        QOMPropertyValue(QOMPropertyTypeInteger, "base", 0),
        QOMPropertyValue(QOMPropertyTypeInteger, "page-base", 0x80),
        QOMPropertyValue(QOMPropertyTypeInteger, "pageh-base", 0xFFFFFFFFFFFFFFFF),
        QOMPropertyValue(QOMPropertyTypeInteger, "dshift", 0),
        ])

    isa_dma_2 = DeviceNode(
        qom_type = "TYPE_I8257",
        parent = self.isa_bus
        )
    isa_dma_2.properties.extend([
        QOMPropertyValue(QOMPropertyTypeInteger, "base", 0xc0),
        QOMPropertyValue(QOMPropertyTypeInteger, "page-base", 0x88),
        QOMPropertyValue(QOMPropertyTypeInteger, "pageh-base", 0xFFFFFFFFFFFFFFFF),
        QOMPropertyValue(QOMPropertyTypeInteger, "dshift", 1),
        ])

    # for 2.6.0 call isa_bus_dma(isa_bus, ISADMA(isa_dma_1), ISADMA(isa_dma_2));
    return self

def old_devices():
    return [
        SysBusDeviceDescription(
            "I/O Port 80", # name
            "i386", # directory
            pio_num = 1
        ),
        SysBusDeviceDescription("I/O Port F0", "i386",
            out_irq_num = 1,
            pio_num = 1
        ),
        SysBusDeviceDescription("A20 Line", "i386",
            in_irq_num = 1
        )
    ]

def Q35Project_2_5_0():
    return QProject(old_devices() + [Q35MachineNode_2_5_0()])

def Q35Project_2_6_0():
    return QProject(old_devices() + [Q35MachineNode_2_6_0()])
