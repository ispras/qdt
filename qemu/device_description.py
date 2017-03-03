from .qom_desc import \
    QOMDescription

from .sysbusdevice import \
    SysBusDeviceType

from .pcie import \
    PCIEDeviceType

from .pci_ids import \
    PCIVendorIdNetherExistsNorCreate, \
    PCIId

class SysBusDeviceDescription(QOMDescription):
    def __init__(self, name, directory,
        out_irq_num = 1,
        in_irq_num = 1,
        mmio_num = 1,
        pio_num = 0,
        **qomd_kw
    ):

        QOMDescription.__init__(self, name, directory, **qomd_kw)
        self.out_irq_num = out_irq_num
        self.in_irq_num = in_irq_num
        self.mmio_num = mmio_num
        self.pio_num = pio_num

    def gen_type(self):
        return SysBusDeviceType(
            name = self.name,
            directory = self.directory,
            char_num = self.char_num,
            timer_num = self.timer_num,
            out_irq_num = self.out_irq_num,
            in_irq_num = self.in_irq_num,
            mmio_num = self.mmio_num,
            pio_num = self.pio_num
            )

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field('name = "' + self.name + '"')
        gen.gen_field('directory = "' + self.directory + '"')
        gen.gen_field("char_num = " + gen.gen_const(self.char_num))
        gen.gen_field("timer_num = " + gen.gen_const(self.timer_num))
        gen.gen_field("out_irq_num = " + str(self.out_irq_num))
        gen.gen_field("in_irq_num = " + str(self.in_irq_num))
        gen.gen_field("mmio_num = " + str(self.mmio_num))
        gen.gen_field("pio_num = " + str(self.pio_num))
        gen.gen_end()

class PCIExpressDeviceDescription(QOMDescription):
    def __init__(self, name, directory, vendor, device, pci_class,
        char_num = 0,
        timer_num = 0,
        irq_num = 0,
        mem_bar_num = 1,
        msi_messages_num = 2,
        revision = 0,
        subsys = None,
        subsys_vendor = None
    ):

        QOMDescription.__init__(self, name, directory,
            char_num = char_num,
            timer_num = timer_num
        )
        self.vendor = vendor
        self.device = device
        self.pci_class = pci_class
        self.irq_num = irq_num
        self.mem_bar_num = mem_bar_num
        self.msi_messages_num = msi_messages_num
        self.revision = revision
        self.subsys = subsys
        self.subsys_vendor = subsys_vendor

    def gen_id_get(self, gen, id):
        if isinstance(id, PCIId):
            id = id.id

        gen.write(gen.gen_const(id))

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field('name = ' + gen.gen_const(self.name))
        gen.gen_field('directory = ' + gen.gen_const(self.directory))
        gen.gen_field('vendor = ')
        self.gen_id_get(gen, self.vendor)
        gen.gen_field('device = ')
        self.gen_id_get(gen, self.device)
        gen.gen_field('pci_class = ')
        self.gen_id_get(gen, self.pci_class)
        gen.gen_field("char_num = " + gen.gen_const(self.char_num))
        gen.gen_field("timer_num = " + gen.gen_const(self.timer_num))
        gen.gen_field("irq_num = " + gen.gen_const(self.irq_num))
        gen.gen_field("mem_bar_num = " + gen.gen_const(self.mem_bar_num))
        gen.gen_field("msi_messages_num = " +
            gen.gen_const(self.msi_messages_num)
        )
        gen.gen_field("revision = " + gen.gen_const(self.revision))
        gen.gen_field('subsys = ')
        self.gen_id_get(gen, self.subsys)
        gen.gen_field('subsys_vendor = ')
        self.gen_id_get(gen, self.subsys_vendor)
        gen.gen_end()

    def gen_type(self):
        kw = {}

        for attr in ["name", "directory", "timer_num", "irq_num",
            "mem_bar_num", "msi_messages_num", "revision", "char_num"
        ]:
            kw[attr] = getattr(self, attr)

        for attr in [ "vendor", "subsys_vendor" ]:
            val = getattr(self, attr)
            if (val is not None) and (not isinstance(val, PCIId)):
                try:
                    val = PCIId.db.get_vendor(name = val)
                except PCIVendorIdNetherExistsNorCreate:
                    val = PCIId.db.get_vendor(vid = val)
            kw[attr] = val

        for attr, vendor in [
            ("device", kw["vendor"]),
            ("subsys", kw["subsys_vendor"])
        ]:
            val = getattr(self, attr)
            if  (val is not None) and (not isinstance(val, PCIId)):
                if vendor is None:
                    raise Exception("Cannot get %s ID descriptor because of no \
corresponding vendor is given" % attr
                    )
                try:
                    val = PCIId.db.get_device(name = val,
                        vendor_name = vendor.name,
                        vid = vendor.id)
                except Exception:
                    val = PCIId.db.get_device(did = val,
                        vendor_name = vendor.name,
                        vid = vendor.id)
            kw[attr] = val

        val = getattr(self, "pci_class")
        # None is not allowed there
        if not isinstance(val, PCIId):
            try:
                val = PCIId.db.get_class(name = val)
            except:
                val = PCIId.db.get_class(cid = val)
        kw["pci_class"] = val

        return PCIEDeviceType(**kw)
