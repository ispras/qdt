from .qom_desc import \
    DescriptionOf, \
    QOMDescription

from .sysbusdevice import \
    SysBusDeviceType

from .pcie import \
    PCIEDeviceType

from .pci_ids import \
    PCIId

@DescriptionOf(SysBusDeviceType)
class SysBusDeviceDescription(QOMDescription):
    pass

@DescriptionOf(PCIEDeviceType)
class PCIExpressDeviceDescription(QOMDescription):
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
        gen.gen_field("block_num = " + gen.gen_const(self.block_num))
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
