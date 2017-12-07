test_device = PCIId.db.get_device(name = "AMD_LANCE",
        vendor_name = "AMD", did = "0x2000")

project = QProject(
    descriptions = [
        PCIExpressDeviceDescription(
            name = "Test PCI NIC",
            directory = "net",
            vendor = "AMD",
            device = test_device,
            subsys = test_device,
            subsys_vendor = "AMD",
            pci_class = "NETWORK_ETHERNET",
            mem_bar_num = 1,
            msi_messages_num = 2
        ),
        SysBusDeviceDescription(
            name = "Dynamips MPC860 CPCR",
            directory = "intc",
            out_irq_num = 0,
            mmio_num = 1,
            pio_num = 0,
            in_irq_num = 0
        )
    ]
)
