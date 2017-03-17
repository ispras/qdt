from source import \
    add_base_types, \
    Pointer, \
    Header,\
    Type, \
    Function, \
    Macro, \
    Structure

from six.moves import \
    range as xrange

def parse_version(ver):
    ver_parts = ver.split(".")

    if ver_parts:
        major = int(ver_parts.pop(0))
    else:
        major = 0

    if ver_parts:
        minor = int(ver_parts.pop(0))
    else:
        minor = 0

    if ver_parts:
        micro = int(ver_parts.pop(0))
    else:
        micro = 0

    if ver_parts:
        suffix = ".".join(ver_parts)
    else:
        suffix = ""

    return (major, minor, micro, suffix)

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
    def __init__(self, name, new_value, old_value = None):
        self.name = name
        self.new_value = new_value
        self.old_value = old_value

    # modification detection code
    def gen_mdc(self):
        if callable(self.new_value):
            nv = self.new_value.__name__
        else:
            nv = self.new_value

        if callable(self.old_value):
            ov = self.old_value.__name__
        else:
            ov = self.old_value

        return self.name + nv + ov

class QEMUVersionDescription(object):
    def __init__(self, version_string, parameters):
        self.version = parse_version(version_string)
        self.parameters = list(parameters)

    def get_parameter(self, name):
        return self.parameters[name]

    def compare(self, version_string):
        version = parse_version(version_string)

        for i in xrange(0, 3):
            if self.version[i] != version[i]:
                return version[i] - self.version[i]

        if self.version[3] == "" and version[3] == "":
            return 0
        raise Exception("Lexical comparation of version suffix is not implemented yet!")

def define_only_qemu_2_6_0_types():
    # According to Qemu inclusion policy, each source file must include
    # qemu/osdep.h. This could be meet using different ways. For now add a
    # reference to a fake type inside osdep.h.
    # TODO: the tweak must be handled using version API.
    osdep_fake_type = Type("FAKE_TYPE_IN_QEMU_OSDEP")

    Header.lookup("qemu/osdep.h").add_types([
        osdep_fake_type
    ])

    Header.lookup("exec/hwaddr.h").add_types([
        Type("hwaddr", False)
    ]).add_reference(osdep_fake_type)

    Header.lookup("exec/cpu-defs.h").add_types([
        Type("target_ulong", False),
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
        Function("object_property_set_int")
    ]).add_reference(osdep_fake_type)

    Header.lookup("qom/cpu.h").add_types([
        Type("CPUState", False),
        Type("CPUClass", False),
        Type("vaddr", False),
        Type("MMUAccessType", False)
    ]).add_reference(osdep_fake_type)

    Header.lookup("exec/exec-all.h").add_types([
        Type("TranslationBlock", False),
        Function('tlb_fill',
                 args = [
                     Type.lookup('CPUState').gen_var('cs', pointer=True),
                     Type.lookup('target_ulong').gen_var('addr'),
                     Type.lookup('MMUAccessType').gen_var('access_type'),
                     Type.lookup('int').gen_var('mmu_idx'),
                     Type.lookup('uintptr_t').gen_var('retaddr')
                 ],
                 used_types = []
                 )
    ]).add_reference(osdep_fake_type)

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
    ]).add_reference(osdep_fake_type)

    Header.lookup("exec/ioport.h").add_types([
        Type("pio_addr_t", incomplete=False)
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
        Function(name = "DeviceRealize"),
        Function(name = "qdev_create"),
        Function(name = "qdev_init_nofail"),
        Function(name = "qdev_get_child_bus"),
        Structure(name = "BusState"),
        Function(name = "qdev_get_gpio_in"),
        Function(name = "qdev_connect_gpio_out"),
        Function(name = "qdev_connect_gpio_out_named")
    ]).add_reference(osdep_fake_type)

    Header.lookup("qapi/error.h").add_types([
        Type("Error")
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
    ]).add_reference(osdep_fake_type)

    Header.lookup("hw/pci/msi.h").add_types([
        Function(name="msi_uninit"
            , ret_type = Type.lookup("void")
            , args = [
                Type.lookup("PCIDevice").gen_var("dev", pointer = True)
            ]
        )
    ]).add_reference(osdep_fake_type)

    Header.lookup("hw/pci/pci_bus.h").add_types([
        Type("PCIBus", incomplete = True)
    ]).add_reference(osdep_fake_type)

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

    Header.lookup("sysemu/char.h").add_types([
        Function("qemu_chr_add_handlers"),
        Structure("CharDriverState"),
        Function("IOEventHandler",
            args = [
                Pointer(Type.lookup("void")).gen_var("opaque"),
                Type.lookup("int").gen_var("event")
            ]
        )
    ]).add_references([
        osdep_fake_type
    ])

    Header.lookup("sysemu/block-backend.h").add_types([
        Structure("BlockDevOps"),
    ]).add_references([
        osdep_fake_type
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
        Function(name="msi_init"
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
    )

# Warning! Preserve order!
qemu_versions = [
    QEMUVersionDescription(
        "2.6.0",
        [
            QEMUVersionParameterDescription(
                name = "machine initialization function register type name",
                new_value = "type_init",
                old_value = "machine_init" 
            )
        ]
    ),
    QEMUVersionDescription(
        "2.6.50",
        [
            QEMUVersionParameterDescription(
                # related commit e8ad4d16808690e9c0d68b140218ca466c9309fc
                name = "qemu types definer",
                new_value = define_qemu_2_6_5_types,
                old_value = define_qemu_2_6_0_types,
            ),
            QEMUVersionParameterDescription(
                # related commit 1108b2f8a939fb5778d384149e2f1b99062a72da
                name = "msi_init type definer",
                new_value = define_msi_init_2_6_5,
                old_value = define_msi_init_2_6_0
            )
        ]
    )
]

qemu_versions_desc = {
        u'8c4575472494a5dfedfe05e7b58ca9ce3872ad56':
        [
            QEMUVersionParameterDescription(
                name = "machine initialization function register type name",
                new_value = "type_init",
                old_value = "machine_init"
            )
        ],
        u'e8ad4d16808690e9c0d68b140218ca466c9309fc':
        [
            QEMUVersionParameterDescription(
                name = "qemu types definer",
                new_value = define_qemu_2_6_5_types,
                old_value = define_qemu_2_6_0_types,
            )
        ],
        u'1108b2f8a939fb5778d384149e2f1b99062a72da':
        [
            QEMUVersionParameterDescription(
                name = "msi_init type definer",
                new_value = define_msi_init_2_6_5,
                old_value = define_msi_init_2_6_0
            )
        ]
}

version_parameters = None
version_string = None

def initialize(_version_string):
    parameters = {}

    for qvd in qemu_versions:
        take_new = qvd.compare(_version_string) >= 0

        for pd in qvd.parameters:
            if pd.name in parameters.keys():
                if take_new:
                    parameters[pd.name] = pd.new_value
            else:
                if take_new:
                    parameters[pd.name] = pd.new_value
                elif pd.old_value is None:
                    raise Exception("No old value for parameter '%s' was found." % pd.name)
                else:
                    parameters[pd.name] = pd.old_value

    global version_parameters
    version_parameters = parameters

    global version_string
    version_string = _version_string

def initialize_version(qvh_vp):
    global version_parameters
    version_parameters = {}
    for k in qvh_vp.keys():
        version_parameters[k] = qvh_vp[k]

def get_vp():
    return version_parameters

def get_vs():
    return version_string
