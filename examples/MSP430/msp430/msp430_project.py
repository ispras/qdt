msp430 = CPUDescription(
    name = "msp430",
    directory = "msp430",
    target_bigendian = False,
    target_long_bits = 0x20,
    target_page_bits = 0x8,
    target_phys_addr_space_bits = 0x20,
    target_virt_addr_space_bits = 0x20,
    nb_mmu_modes = 0x1,
    info_path = "msp430_sem.py"
)

msp430_hwm = SysBusDeviceDescription(
    name = "MSP430 HWM",
    directory = "msp430-all",
    out_irq_num = 0,
    in_irq_num = 0,
    mmio_num = 0x1,
    pio_num = 0,
    mmio = {
        0: [
            Register(2, name = 'MPY', reset = None, full_name = '16-bit operand one - multiply'),
            Register(2, name = 'MPYS', reset = None, full_name = '16-bit operand one - signed multiply'),
            Register(2, name = 'MAC', reset = None, full_name = '16-bit operand one - multiply accumulate'),
            Register(2, name = 'MACS', reset = None, full_name = '16-bit operand one - signed multiply accumulate'),
            Register(2, name = 'OP2', reset = None, full_name = '16-bit operand two'),
            Register(2, name = 'RESLO', reset = None, full_name = '16x16-bit result low word'),
            Register(2, name = 'RESHI', reset = None, full_name = '16x16-bit result high word'),
            Register(2, name = 'SUMEXT', access = 'r', reset = None, full_name = '16x16-bit sum extension register'),
            Register(2, name = 'MPY32L', reset = None, full_name = '32-bit operand 1 - multiply - low word'),
            Register(2, name = 'MPY32H', reset = None, full_name = '32-bit operand 1 - multiply - high word'),
            Register(2, name = 'MPYS32L', reset = None, full_name = '32-bit operand 1 - signed multiply - low word'),
            Register(2, name = 'MPYS32H', reset = None, full_name = '32-bit operand 1 - signed multiply - high word'),
            Register(2, name = 'MAC32L', reset = None, full_name = '32-bit operand 1 - multiply accumulate - low word'),
            Register(2, name = 'MAC32H', reset = None, full_name = '32-bit operand 1 - multiply accumulate - high word'),
            Register(2, name = 'MACS32L', reset = None, full_name = '32-bit operand 1 - signed multiply accumulate - low word'),
            Register(2, name = 'MACS32H', reset = None, full_name = '32-bit operand 1 - signed multiply accumulate - high word'),
            Register(2, name = 'OP2L', reset = None, full_name = '32-bit operand 2 - low word'),
            Register(2, name = 'OP2H', reset = None, full_name = '32-bit operand 2 - high word'),
            Register(2, name = 'RES0', reset = None, full_name = '32x32-bit result 0 - least significant word'),
            Register(2, name = 'RES1', reset = None, full_name = '32x32-bit result 1'),
            Register(2, name = 'RES2', reset = None, full_name = '32x32-bit result 2'),
            Register(2, name = 'RES3', reset = None, full_name = '32x32-bit result 3 - most significant word'),
            Register(2, name = 'MPY32CTL0', full_name = 'MPY32 control register 0', wmask = CINT(0x03FD, 16, 4))
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0,
    char_num = 0,
    block_num = 0
)

cpu = CPUNode(
    qom_type = "msp430-cpu"
)

bus = SystemBusNode()

hwm = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_HWM",
    system_bus = bus,
    mmio = [
        0x138
    ],
    var_base = "hwm"
)

hwm.properties.extend([
    QOMPropertyValue(QOMPropertyTypeBoolean, "op-32-bit", True)
])

mem = MemorySASNode(
    name = CSTR('System address space')
)

ram = MemoryRAMNode(
    name = CSTR('RAM'),
    size = CINT(512, 10, 3),
    var_base = "ram"
)
mem.add_child(
    child = ram,
    offset = CINT(0x200, 16, 3),
    priority = CINT(1, 10, 0)
)

rom = MemoryRAMNode(
    name = CSTR('ROM'),
    size = CINT(0xFC00, 16, 4),
    var_base = "rom"
)
mem.add_child(
    child = rom,
    offset = CINT(0x400, 16, 3),
    priority = CINT(1, 10, 0)
)

msp430_test = MachineDescription(
    name = "msp430-test",
    directory = "msp430"
)
msp430_test.add_node(bus, with_id = 0)
msp430_test.add_node(cpu, with_id = 1)
msp430_test.add_node(hwm, with_id = 2)
msp430_test.add_node(mem, with_id = 3)
msp430_test.add_node(ram, with_id = 4)
msp430_test.add_node(rom, with_id = 6)

msp430_hwm_l0 = GUILayout(
    desc_name = "MSP430 HWM",
    opaque = {},
    shown = False
)
msp430_hwm_l0.lid = 0

msp430_l0 = GUILayout(
    desc_name = "msp430",
    opaque = {},
    shown = False
)
msp430_l0.lid = 0

obj = MachineWidgetLayout(
    mdwl = {
        -1: {
            "IRQ lines points": {},
            "mesh step": 0x14,
            "physical layout": False,
            "show mesh": False
        },
        0: (
            322.0,
            300.0
        ),
        0x1: (
            300.0,
            200.0
        ),
        0x2: (
            360.0,
            380.0
        )
    },
    mtwl = {
        -1: {
            "columns width": {
                "#0": 0xc8,
                "id": 0xc8,
                "offset": 0xc8,
                "size": 0xc8,
                "type": 0xc8
            }
        }
    },
    use_tabs = True
)

msp430_test_l0 = GUILayout(
    desc_name = "msp430-test",
    opaque = obj,
    shown = True
)
msp430_test_l0.lid = 0

project = GUIProject(
    layouts = [
        msp430_hwm_l0,
        msp430_l0,
        msp430_test_l0
    ],
    target_version = "v5.1.0",
    descriptions = [
        msp430,
        msp430_hwm,
        msp430_test
    ]
)

