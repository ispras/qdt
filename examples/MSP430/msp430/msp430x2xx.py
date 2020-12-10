cpu = CPUNode(
    qom_type = "msp430-cpu"
)

bus = SystemBusNode()

bcm = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_BCM",
    system_bus = bus,
    mmio = [
        0x53,
        0x56
    ],
    var_base = "bcm"
)

dma = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_DMA",
    system_bus = bus,
    mmio = [
        0x122,
        0x1d0
    ],
    var_base = "dma"
)

ic = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_IC",
    system_bus = bus,
    mmio = [
        0
    ],
    var_base = "ic"
)

ic.properties.extend([
    QOMPropertyValue(QOMPropertyTypeLink, "cpu", cpu)
])

fmc = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_FMC",
    system_bus = bus,
    mmio = [
        0x128,
        0x1be,
        0x1000,
        0x8000
    ],
    var_base = "fmc"
)

fmc.properties.extend([
    QOMPropertyValue(QOMPropertyTypeString, "blk", "pflash0")
])

io = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_IO",
    system_bus = bus,
    mmio = [
        0x10
    ],
    var_base = "io"
)

svs = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_SVS",
    system_bus = bus,
    mmio = [
        0x55
    ],
    var_base = "svs"
)

wdt = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_WDT",
    system_bus = bus,
    mmio = [
        0x120
    ],
    var_base = "wdt"
)

# Use HWM from CPU simple board model definition
hwm = SystemBusDeviceNode(
    qom_type = "msp430_hwm",
    system_bus = bus,
    mmio = [
        0x130
    ],
    var_base = "hwm"
)

hwm.properties.extend([
    QOMPropertyValue(QOMPropertyTypeBoolean, "op-32-bit", False)
])

timer_a = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_TIMER_A",
    system_bus = bus,
    mmio = [
        0x160,
        0x12e
    ],
    var_base = "timer_a"
)

timer_b = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_TIMER_B",
    system_bus = bus,
    mmio = [
        0x180,
        0x11e
    ],
    var_base = "timer_b"
)

usi = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_USI",
    system_bus = bus,
    mmio = [
        0x78
    ],
    var_base = "usi"
)

oa0 = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_OA",
    system_bus = bus,
    mmio = [
        0xc0
    ],
    var_base = "oa0"
)

oa1 = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_OA",
    system_bus = bus,
    mmio = [
        0xc2
    ],
    var_base = "oa1"
)

oa2 = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_OA",
    system_bus = bus,
    mmio = [
        0xc4
    ],
    var_base = "oa2"
)

comp_a = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_COMP_A",
    system_bus = bus,
    mmio = [
        0x59
    ],
    var_base = "comp_a"
)

adc10 = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_ADC10",
    system_bus = bus,
    mmio = [
        0x48,
        0x1b0
    ],
    var_base = "adc10"
)

adc12 = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_ADC12",
    system_bus = bus,
    mmio = [
        0x1a0,
        0x140,
        0x80
    ],
    var_base = "adc12"
)

dac12_0 = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_DAC12",
    system_bus = bus,
    mmio = [
        0x1c0,
        0x1c8
    ],
    var_base = "dac12_0"
)

dac12_1 = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_DAC12",
    system_bus = bus,
    mmio = [
        0x1c2,
        0x1ca
    ],
    var_base = "dac12_1"
)

sd16_a = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_SD16_A",
    system_bus = bus,
    mmio = [
        0x100,
        0xb0
    ],
    var_base = "sd16_a"
)

usci_a = SystemBusDeviceNode(
    qom_type = "TYPE_MSP430_USCI_A",
    system_bus = bus,
    mmio = [
        0x5d
    ],
    var_base = "usci_a"
)

usci_a.properties.extend([
    QOMPropertyValue(QOMPropertyTypeString, "chr", "serial0")
])

irq_usci_a_rx_to_ic_8 = IRQLine(
    src_dev = usci_a,
    dst_dev = ic,
    dst_irq_idx = 0x8,
    src_irq_name = "SYSBUS_DEVICE_GPIO_IRQ",
    var_base = "irq_usci_a_rx_to_ic_8"
)

irq_usci_a_swrst_to_ic_9 = IRQLine(
    src_dev = usci_a,
    dst_dev = ic,
    src_irq_idx = 0x1,
    dst_irq_idx = 0x9,
    src_irq_name = "SYSBUS_DEVICE_GPIO_IRQ",
    var_base = "irq_usci_a_swrst_to_ic_9"
)

irq_wdt_0_to_ic_0 = IRQLine(
    src_dev = wdt,
    dst_dev = ic,
    src_irq_name = "SYSBUS_DEVICE_GPIO_IRQ",
    var_base = "irq_wdt_0_to_ic_0"
)

mem = MemorySASNode(
    name = CSTR('System address space')
)

ram = MemoryRAMNode(
    name = CSTR('RAM'),
    size = CINT(0x200, 16, 3),
    var_base = "ram"
)
mem.add_child(
    child = ram,
    offset = CINT(0x200, 16, 3),
    priority = CINT(1, 10, 0)
)

msp430x2xx = MachineDescription(
    name = "msp430x2xx",
    directory = "msp430"
)
msp430x2xx.add_node(bus, with_id = 0)
msp430x2xx.add_node(cpu, with_id = 1)
msp430x2xx.add_node(mem, with_id = 2)
msp430x2xx.add_node(ram, with_id = 3)
msp430x2xx.add_node(bcm, with_id = 4)
msp430x2xx.add_node(dma, with_id = 5)
msp430x2xx.add_node(ic, with_id = 6)
msp430x2xx.add_node(fmc, with_id = 7)
msp430x2xx.add_node(io, with_id = 8)
msp430x2xx.add_node(svs, with_id = 9)
msp430x2xx.add_node(wdt, with_id = 10)
msp430x2xx.add_node(hwm, with_id = 11)
msp430x2xx.add_node(timer_a, with_id = 12)
msp430x2xx.add_node(timer_b, with_id = 13)
msp430x2xx.add_node(usi, with_id = 14)
msp430x2xx.add_node(oa0, with_id = 15)
msp430x2xx.add_node(oa1, with_id = 16)
msp430x2xx.add_node(oa2, with_id = 17)
msp430x2xx.add_node(comp_a, with_id = 18)
msp430x2xx.add_node(adc10, with_id = 19)
msp430x2xx.add_node(adc12, with_id = 20)
msp430x2xx.add_node(dac12_0, with_id = 21)
msp430x2xx.add_node(dac12_1, with_id = 22)
msp430x2xx.add_node(sd16_a, with_id = 23)
msp430x2xx.add_node(usci_a, with_id = 24)
msp430x2xx.add_node(irq_usci_a_rx_to_ic_8, with_id = 25)
msp430x2xx.add_node(irq_usci_a_swrst_to_ic_9, with_id = 26)
msp430x2xx.add_node(irq_wdt_0_to_ic_0, with_id = 27)

msp430_bcm = SysBusDeviceDescription(
    name = "MSP430 BCM+",
    directory = "msp430",
    out_irq_num = 0x1,
    in_irq_num = 0,
    mmio_num = 0x2,
    pio_num = 0,
    mmio = {
        0: [
            Register(1, name = 'BCSCTL3', reset = CINT(0b00000101, 2, 8), full_name = 'Basic clock system control 3', wmask = CINT(0b11111100, 2, 8))
        ],
        0x1: [
            Register(1, name = 'DCOCTL', reset = CINT(0b01100000, 2, 8), full_name = 'DCO control register'),
            Register(1, name = 'BCSCTL1', reset = CINT(0b10000111, 2, 8), full_name = 'Basic clock system control 1'),
            Register(1, name = 'BCSCTL2', full_name = 'Basic clock system control 2')
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0,
    char_num = 0,
    block_num = 0
)

msp430_dma = SysBusDeviceDescription(
    name = "MSP430 DMA",
    directory = "msp430",
    out_irq_num = 0,
    in_irq_num = 0,
    mmio_num = 0x2,
    pio_num = 0,
    mmio = {
        0: [
            Register(2, name = 'DMACTL0', full_name = 'DMA Control Register 0'),
            Register(2, name = 'DMACTL1', full_name = 'DMA Control Register 1', wmask = CINT(0x0007, 16, 4)),
            Register(2, name = 'DMAIV', full_name = 'DMA Interrupt Vector Register', wmask = CINT(0b0000000000000000, 2, 16))
        ],
        0x1: [
            Register(2, name = 'DMA0CTL', full_name = 'DMA channel 0 control'),
            Register(4, name = 'DMA0SA', reset = None, full_name = 'DMA channel 0 source address', wmask = CINT(0x000FFFFF, 16, 8)),
            Register(4, name = 'DMA0DA', reset = None, full_name = 'DMA channel 0 destination address', wmask = CINT(0x000FFFFF, 16, 8)),
            Register(2, name = 'DMA0SZ', reset = None, full_name = 'DMA channel 0 transfer size'),
            Register(2, name = 'DMA1CTL', full_name = 'DMA channel 1 control'),
            Register(4, name = 'DMA1SA', reset = None, full_name = 'DMA channel 1 source address', wmask = CINT(0x000FFFFF, 16, 8)),
            Register(4, name = 'DMA1DA', reset = None, full_name = 'DMA channel 1 destination address', wmask = CINT(0x000FFFFF, 16, 8)),
            Register(2, name = 'DMA1SZ', reset = None, full_name = 'DMA channel 1 transfer size'),
            Register(2, name = 'DMA2CTL', full_name = 'DMA channel 2 control'),
            Register(4, name = 'DMA2SA', reset = None, full_name = 'DMA channel 2 source address', wmask = CINT(0x000FFFFF, 16, 8)),
            Register(4, name = 'DMA2DA', reset = None, full_name = 'DMA channel 2 destination address', wmask = CINT(0x000FFFFF, 16, 8)),
            Register(2, name = 'DMA2SZ', reset = None, full_name = 'DMA channel 2 transfer size')
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0,
    char_num = 0,
    block_num = 0
)

msp430_ic = SysBusDeviceDescription(
    name = "MSP430 IC",
    directory = "msp430",
    out_irq_num = 0,
    in_irq_num = 0x20,
    mmio_num = 0x1,
    pio_num = 0,
    mmio = {
        0: [
            Register(1, name = 'IE1'),
            Register(1, name = 'IE2'),
            Register(1, name = 'IFG1'),
            Register(1, name = 'IFG2')
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0,
    char_num = 0,
    block_num = 0
)

msp430_fmc = SysBusDeviceDescription(
    name = "MSP430 FMC",
    directory = "msp430",
    out_irq_num = 0,
    in_irq_num = 0,
    mmio_num = 0x4,
    pio_num = 0,
    mmio = {
        0: [
            Register(2, name = 'FCTL1', reset = CINT(0x9600, 16, 4), full_name = 'Flash memory control register 1', wmask = CINT(0x00DE, 16, 4)),
            Register(2, name = 'FCTL2', reset = CINT(0x9642, 16, 4), full_name = 'Flash memory control register 2', wmask = CINT(0x00FF, 16, 4)),
            Register(2, name = 'FCTL3', reset = CINT(0x9658, 16, 4), full_name = 'Flash memory control register 3', wmask = CINT(0x00F7, 16, 4))
        ],
        0x1: [
            Register(2, name = 'FCTL4', full_name = 'Flash memory control register 4', wmask = CINT(0x0030, 16, 4))
        ],
        0x2: MemoryROMNode(
            name = CSTR('Information Memory'),
            size = CINT(512, 10, 0),
            var_base = "info"
        ),
        0x3: MemoryROMNode(
            name = CSTR('Main Memory'),
            size = CINT(32768, 10, 0)
        )
    },
    pio = None,
    nic_num = 0,
    timer_num = 0,
    char_num = 0,
    block_num = 0x1
)

# Port 8 is disabled because it overlaps with ADC10:
# P8SEL2 and ADC10DTC0 at 0x48
msp430_io = SysBusDeviceDescription(
    name = "MSP430 IO",
    directory = "msp430",
    out_irq_num = 0x2,
    in_irq_num = 0,
    mmio_num = 0x1,
    pio_num = 0,
    mmio = {
        0: [
            Register(1, name = 'P3REN', full_name = 'P3 Resistor Enable'),
            Register(1, name = 'P4REN', full_name = 'P4 Resistor Enable'),
            Register(1, name = 'P5REN', full_name = 'P5 Resistor Enable'),
            Register(1, name = 'P6REN', full_name = 'P6 Resistor Enable'),
            Register(1, name = 'P7REN', full_name = 'P7 Resistor Enable'),
            Register(1, name = 'gap'),
            Register(1, name = 'gap'),
            Register(1, name = 'gap'),
            Register(1, name = 'P3IN', access = 'r', full_name = 'P3 Input'),
            Register(1, name = 'P3OUT', reset = None, full_name = 'P3 Output'),
            Register(1, name = 'P3DIR', full_name = 'P3 Direction'),
            Register(1, name = 'P3SEL', full_name = 'P3 Port Select'),
            Register(1, name = 'P4IN', access = 'r', full_name = 'P4 Input'),
            Register(1, name = 'P4OUT', reset = None, full_name = 'P4 Output'),
            Register(1, name = 'P4DIR', full_name = 'P4 Direction'),
            Register(1, name = 'P4SEL', full_name = 'P4 Port Select'),
            Register(1, name = 'P1IN', access = 'r', full_name = 'P1 Input'),
            Register(1, name = 'P1OUT', reset = None, full_name = 'P1 Output'),
            Register(1, name = 'P1DIR', full_name = 'P1 Direction'),
            Register(1, name = 'P1IFG', full_name = 'P1 Interrupt Flag'),
            Register(1, name = 'P1IES', reset = None, full_name = 'P1 Interrupt Edge Select'),
            Register(1, name = 'P1IE', full_name = 'P1 Interrupt Enable'),
            Register(1, name = 'P1SEL', full_name = 'P1 Port Select'),
            Register(1, name = 'P1REN', full_name = 'P1 Resistor Enable'),
            Register(1, name = 'P2IN', access = 'r', full_name = 'P2 Input'),
            Register(1, name = 'P2OUT', reset = None, full_name = 'P2 Output'),
            Register(1, name = 'P2DIR', full_name = 'P2 Direction'),
            Register(1, name = 'P2IFG', full_name = 'P2 Interrupt Flag'),
            Register(1, name = 'P2IES', reset = None, full_name = 'P2 Interrupt Edge Select'),
            Register(1, name = 'P2IE', full_name = 'P2 Interrupt Enable'),
            Register(1, name = 'P2SEL', reset = CINT(0xC0, 16, 2), full_name = 'P2 Port Select'),
            Register(1, name = 'P2REN', full_name = 'P2 Resistor Enable'),
            Register(1, name = 'P5IN', access = 'r', full_name = 'P5 Input'),
            Register(1, name = 'P5OUT', reset = None, full_name = 'P5 Output'),
            Register(1, name = 'P5DIR', full_name = 'P5 Direction'),
            Register(1, name = 'P5SEL', full_name = 'P5 Port Select'),
            Register(1, name = 'P6IN', access = 'r', full_name = 'P6 Input'),
            Register(1, name = 'P6OUT', reset = None, full_name = 'P6 Output'),
            Register(1, name = 'P6DIR', full_name = 'P6 Direction'),
            Register(1, name = 'P6SEL', full_name = 'P6 Port Select'),
            Register(1, name = 'P7IN', access = 'r', full_name = 'P7 Input'),
            Register(1, name = 'gap'),
            Register(1, name = 'P7OUT', reset = None, full_name = 'P7 Output'),
            Register(1, name = 'gap'),
            Register(1, name = 'P7DIR', full_name = 'P7 Direction'),
            Register(1, name = 'gap'),
            Register(1, name = 'P7SEL', full_name = 'P7 Port Select'),
            Register(1, name = 'gap'),
            Register(1, name = 'gap'),
            Register(1, name = 'P1SEL2', full_name = 'P1 Port Select 2'),
            Register(1, name = 'P2SEL2', full_name = 'P2 Port Select 2'),
            Register(1, name = 'P3SEL2', full_name = 'P3 Port Select 2'),
            Register(1, name = 'P4SEL2', full_name = 'P4 Port Select 2'),
            Register(1, name = 'P5SEL2', full_name = 'P5 Port Select 2'),
            Register(1, name = 'P6SEL2', full_name = 'P6 Port Select 2'),
            Register(1, name = 'P7SEL2', full_name = 'P7 Port Select 2')
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0,
    char_num = 0,
    block_num = 0
)

msp430_svs = SysBusDeviceDescription(
    name = "MSP430 SVS",
    directory = "msp430",
    out_irq_num = 0,
    in_irq_num = 0,
    mmio_num = 0x1,
    pio_num = 0,
    mmio = {
        0: [
            Register(1, name = 'SVSCTL', full_name = 'SVS Control Register')
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0,
    char_num = 0,
    block_num = 0
)

msp430_wdt = SysBusDeviceDescription(
    name = "MSP430 WDT+",
    directory = "msp430",
    out_irq_num = 0x1,
    in_irq_num = 0,
    mmio_num = 0x1,
    pio_num = 0,
    mmio = {
        0: [
            Register(2, name = 'WDTCTL', reset = CINT(0x6900, 16, 4), full_name = 'Watchdog timer+ control register', wmask = CINT(0x00FF, 16, 4))
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0x1,
    char_num = 0,
    block_num = 0
)

msp430_timer_a = SysBusDeviceDescription(
    name = "MSP430 Timer A",
    directory = "msp430",
    out_irq_num = 0,
    in_irq_num = 0,
    mmio_num = 0x2,
    pio_num = 0,
    mmio = {
        0: [
            Register(2, name = 'TACTL', full_name = 'Timer_A control'),
            Register(2, name = 'TACCTL0', full_name = 'Timer_A capture/compare control 0', wmask = CINT(0b1111100111110111, 2, 16)),
            Register(2, name = 'TACCTL1', full_name = 'Timer_A capture/compare control 1', wmask = CINT(0b1111100111110111, 2, 16)),
            Register(2, name = 'TACCTL2', full_name = 'Timer_A capture/compare control 2', wmask = CINT(0b1111100111110111, 2, 16)),
            Register(8),
            Register(2, name = 'TAR', full_name = 'Timer_A counter'),
            Register(2, name = 'TACCR0', full_name = 'Timer_A capture/compare 0'),
            Register(2, name = 'TACCR1', full_name = 'Timer_A capture/compare 1'),
            Register(2, name = 'TACCR2', full_name = 'Timer_A capture/compare 2')
        ],
        0x1: [
            Register(2, name = 'TAIV', access = 'r', full_name = 'Timer_A interrupt vector')
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0x1,
    char_num = 0,
    block_num = 0
)

msp430_timer_b = SysBusDeviceDescription(
    name = "MSP430 Timer B",
    directory = "msp430",
    out_irq_num = 0,
    in_irq_num = 0,
    mmio_num = 0x2,
    pio_num = 0,
    mmio = {
        0: [
            Register(2, name = 'TBCTL', full_name = 'Timer_B control'),
            Register(2, name = 'TBCCTL0', full_name = 'Timer_B capture/compare control 0', wmask = CINT(0b1111110111110111, 2, 16)),
            Register(2, name = 'TBCCTL1', full_name = 'Timer_B capture/compare control 1', wmask = CINT(0b1111110111110111, 2, 16)),
            Register(2, name = 'TBCCTL2', full_name = 'Timer_B capture/compare control 2', wmask = CINT(0b1111110111110111, 2, 16)),
            Register(2, name = 'TBCCTL3', full_name = 'Timer_B capture/compare control 3', wmask = CINT(0b1111110111110111, 2, 16)),
            Register(2, name = 'TBCCTL4', full_name = 'Timer_B capture/compare control 4', wmask = CINT(0b1111110111110111, 2, 16)),
            Register(2, name = 'TBCCTL5', full_name = 'Timer_B capture/compare control 5', wmask = CINT(0b1111110111110111, 2, 16)),
            Register(2, name = 'TBCCTL6', full_name = 'Timer_B capture/compare control 6', wmask = CINT(0b1111110111110111, 2, 16)),
            Register(2, name = 'TBR', full_name = 'Timer_B counter'),
            Register(2, name = 'TBCCR0', full_name = 'Timer_B capture/compare 0'),
            Register(2, name = 'TBCCR1', full_name = 'Timer_B capture/compare 1'),
            Register(2, name = 'TBCCR2', full_name = 'Timer_B capture/compare 2'),
            Register(2, name = 'TBCCR3', full_name = 'Timer_B capture/compare 3'),
            Register(2, name = 'TBCCR4', full_name = 'Timer_B capture/compare 4'),
            Register(2, name = 'TBCCR5', full_name = 'Timer_B capture/compare 5'),
            Register(2, name = 'TBCCR6', full_name = 'Timer_B capture/compare 6')
        ],
        0x1: [
            Register(2, name = 'TBIV', access = 'r', full_name = 'Timer_B interrupt vector')
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0x1,
    char_num = 0,
    block_num = 0
)

msp430_usi = SysBusDeviceDescription(
    name = "MSP430 USI",
    directory = "msp430",
    out_irq_num = 0x1,
    in_irq_num = 0,
    mmio_num = 0x1,
    pio_num = 0,
    mmio = {
        0: [
            Register(1, name = 'USICTL0', reset = CINT(0x01, 16, 2), full_name = 'USI control register 0'),
            Register(1, name = 'USICTL1', reset = CINT(0x01, 16, 2), full_name = 'USI control register 1'),
            Register(1, name = 'USICKCTL', full_name = 'USI clock control'),
            Register(1, name = 'USICNT', full_name = 'USI bit counter'),
            Register(1, name = 'USISRL', reset = None, full_name = 'USI low byte shift register'),
            Register(1, name = 'USISRH', reset = None, full_name = 'USI high byte shift register')
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0,
    char_num = 0,
    block_num = 0
)

msp430_oa = SysBusDeviceDescription(
    name = "MSP430 OA",
    directory = "msp430",
    out_irq_num = 0,
    in_irq_num = 0,
    mmio_num = 0x1,
    pio_num = 0,
    mmio = {
        0: [
            Register(1, name = 'OAxCTL0', full_name = 'OAx control register 0'),
            Register(1, name = 'OAxCTL1', full_name = 'OAx control register 1')
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0,
    char_num = 0,
    block_num = 0
)

msp430_comp_a = SysBusDeviceDescription(
    name = "MSP430 Comp A+",
    directory = "msp430",
    out_irq_num = 0x1,
    in_irq_num = 0,
    mmio_num = 0x1,
    pio_num = 0,
    mmio = {
        0: [
            Register(1, name = 'CACTL1', full_name = 'Comparator_A+ control register 1'),
            Register(1, name = 'CACTL2', full_name = 'Comparator_A+ control register 2', wmask = CINT(0b11111110, 2, 8)),
            Register(1, name = 'CAPD', full_name = 'Comparator_A+ port disable')
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0,
    char_num = 0,
    block_num = 0
)

msp430_adc10 = SysBusDeviceDescription(
    name = "MSP430 ADC10",
    directory = "msp430",
    out_irq_num = 0,
    in_irq_num = 0,
    mmio_num = 0x2,
    pio_num = 0,
    mmio = {
        0: [
            Register(1, name = 'ADC10DTC0', full_name = 'ADC10 data transfer control register 0', wmask = CINT(0b00001101, 2, 8)),
            Register(1, name = 'ADC10DTC1', full_name = 'ADC10 data transfer control register 1'),
            Register(1, name = 'ADC10AE0', full_name = 'ADC10 input enable register 0'),
            Register(1, name = 'ADC10AE1', full_name = 'ADC10 input enable register 1')
        ],
        0x1: [
            Register(2, name = 'ADC10CTL0', full_name = 'ADC10 control register 0'),
            Register(2, name = 'ADC10CTL1', full_name = 'ADC10 control register 1', wmask = CINT(0xFFFE, 16, 4)),
            Register(2, name = 'ADC10MEM', access = 'r', reset = None, full_name = 'ADC10 memory'),
            Register(6),
            Register(2, name = 'ADC10SA', reset = CINT(0x0200, 16, 4), full_name = 'ADC10 data transfer start address', wmask = CINT(0xFFFE, 16, 4))
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0x1,
    char_num = 0,
    block_num = 0
)

msp430_adc12 = SysBusDeviceDescription(
    name = "MSP430 ADC12",
    directory = "msp430",
    out_irq_num = 0x1,
    in_irq_num = 0,
    mmio_num = 0x3,
    pio_num = 0,
    mmio = {
        0: [
            Register(2, name = 'ADC12CTL0', full_name = 'ADC12 control register 0'),
            Register(2, name = 'ADC12CTL1', full_name = 'ADC12 control register 1'),
            Register(2, name = 'ADC12IFG', full_name = 'ADC12 interrupt flag register'),
            Register(2, name = 'ADC12IE', full_name = 'ADC12 interrupt enable register'),
            Register(2, name = 'ADC12IV', access = 'r', full_name = 'ADC12 interrupt vector word')
        ],
        0x1: MemoryROMNode(
            name = CSTR('ADC12 memory'),
            size = CINT(32, 10, 0)
        ),
        0x2: MemoryROMNode(
            name = CSTR('ADC12 memory control'),
            size = CINT(16, 10, 0),
            var_base = "ctl"
        )
    },
    pio = None,
    nic_num = 0,
    timer_num = 0,
    char_num = 0,
    block_num = 0
)

msp430_dac12 = SysBusDeviceDescription(
    name = "MSP430 DAC12",
    directory = "msp430",
    out_irq_num = 0x1,
    in_irq_num = 0,
    mmio_num = 0x2,
    pio_num = 0,
    mmio = {
        0: [
            Register(2, name = 'DAC12_xCTL', full_name = 'DAC12_x control')
        ],
        0x1: [
            Register(2, name = 'DAC12_xDAT', full_name = 'DAC12_x data', wmask = CINT(0x0FFF, 16, 4))
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0,
    char_num = 0,
    block_num = 0
)

msp430_sd16_a = SysBusDeviceDescription(
    name = "MSP430 SD16_A",
    directory = "msp430",
    out_irq_num = 0x2,
    in_irq_num = 0,
    mmio_num = 0x2,
    pio_num = 0,
    mmio = {
        0: [
            Register(2, name = 'SD16CTL', full_name = 'SD16_A control', wmask = CINT(0x0FFE, 16, 4)),
            Register(2, name = 'SD16CCTL0', full_name = 'SD16_A channel 0 control', wmask = CINT(0x7FFE, 16, 4)),
            Register(14),
            Register(2, name = 'SD16IV', access = 'r', full_name = 'SD16_A interrupt vector'),
            Register(2, name = 'SD16MEM0', access = 'r', full_name = 'SD16_A conversion memory')
        ],
        0x1: [
            Register(1, name = 'SD16INCTL0', full_name = 'SD16_A input control'),
            Register(6),
            Register(1, name = 'SD16AE', full_name = 'SD16_A analog enable')
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0,
    char_num = 0,
    block_num = 0
)

msp430_usci_a = SysBusDeviceDescription(
    name = "MSP430 USCI_A",
    directory = "msp430",
    out_irq_num = 0x2,
    in_irq_num = 0,
    mmio_num = 0x1,
    pio_num = 0,
    mmio = {
        0: [
            Register(1, name = 'UCAxABCTL', full_name = 'USCI_Ax Auto baud control register'),
            Register(1, name = 'UCAxIRTCTL', full_name = 'USCI_Ax IrDA transmit control register'),
            Register(1, name = 'UCAxIRRCTL', full_name = 'USCI_Ax IrDA receive control register'),
            Register(1, name = 'UCAxCTL0', full_name = 'USCI_Ax control register 0'),
            Register(1, name = 'UCAxCTL1', reset = CINT(0x01, 16, 2), full_name = 'USCI_Ax control register 1'),
            Register(1, name = 'UCAxBR0', full_name = 'USCI_Ax Baud rate control register 0'),
            Register(1, name = 'UCAxBR1', full_name = 'USCI_Ax Baud rate control register 1'),
            Register(1, name = 'UCAxMCTL', full_name = 'USCI_Ax modulation control register'),
            Register(1, name = 'UCAxSTAT', full_name = 'USCI_Ax status register'),
            Register(1, name = 'UCAxRXBUF', access = 'r', full_name = 'USCI_Ax receive buffer register'),
            Register(1, name = 'UCAxTXBUF', full_name = 'USCI_Ax transmit buffer register')
        ]
    },
    pio = None,
    nic_num = 0,
    timer_num = 0,
    char_num = 0x1,
    block_num = 0
)

msp430_adc10_l0 = GUILayout(
    desc_name = "MSP430 ADC10",
    opaque = {},
    shown = False
)
msp430_adc10_l0.lid = 0

msp430_adc12_l0 = GUILayout(
    desc_name = "MSP430 ADC12",
    opaque = {},
    shown = False
)
msp430_adc12_l0.lid = 0

msp430_bcm_l0 = GUILayout(
    desc_name = "MSP430 BCM+",
    opaque = {},
    shown = False
)
msp430_bcm_l0.lid = 0

msp430_comp_a_l0 = GUILayout(
    desc_name = "MSP430 Comp A+",
    opaque = {},
    shown = False
)
msp430_comp_a_l0.lid = 0

msp430_dac12_l0 = GUILayout(
    desc_name = "MSP430 DAC12",
    opaque = {},
    shown = False
)
msp430_dac12_l0.lid = 0

msp430_dma_l0 = GUILayout(
    desc_name = "MSP430 DMA",
    opaque = {},
    shown = False
)
msp430_dma_l0.lid = 0

msp430_fmc_l0 = GUILayout(
    desc_name = "MSP430 FMC",
    opaque = {},
    shown = False
)
msp430_fmc_l0.lid = 0

msp430_ic_l0 = GUILayout(
    desc_name = "MSP430 IC",
    opaque = {},
    shown = False
)
msp430_ic_l0.lid = 0

msp430_io_l0 = GUILayout(
    desc_name = "MSP430 IO",
    opaque = {},
    shown = False
)
msp430_io_l0.lid = 0

msp430_oa_l0 = GUILayout(
    desc_name = "MSP430 OA",
    opaque = {},
    shown = False
)
msp430_oa_l0.lid = 0

msp430_sd16_a_l0 = GUILayout(
    desc_name = "MSP430 SD16_A",
    opaque = {},
    shown = False
)
msp430_sd16_a_l0.lid = 0

msp430_svs_l0 = GUILayout(
    desc_name = "MSP430 SVS",
    opaque = {},
    shown = False
)
msp430_svs_l0.lid = 0

msp430_timer_a_l0 = GUILayout(
    desc_name = "MSP430 Timer A",
    opaque = {},
    shown = False
)
msp430_timer_a_l0.lid = 0

msp430_timer_b_l0 = GUILayout(
    desc_name = "MSP430 Timer B",
    opaque = {},
    shown = False
)
msp430_timer_b_l0.lid = 0

msp430_usci_a_l0 = GUILayout(
    desc_name = "MSP430 USCI_A",
    opaque = {},
    shown = False
)
msp430_usci_a_l0.lid = 0

msp430_usi_l0 = GUILayout(
    desc_name = "MSP430 USI",
    opaque = {},
    shown = False
)
msp430_usi_l0.lid = 0

msp430_wdt_l0 = GUILayout(
    desc_name = "MSP430 WDT+",
    opaque = {},
    shown = False
)
msp430_wdt_l0.lid = 0

obj = MachineWidgetLayout(
    mdwl = {
        -1: {
            "IRQ lines points": {
                0x19: [
                    (
                        31.0,
                        452.0
                    ),
                    (
                        37.0,
                        200.0
                    )
                ],
                0x1a: [
                    (
                        42.0,
                        440.0
                    ),
                    (
                        47.0,
                        212.0
                    )
                ],
                0x1b: []
            },
            "mesh step": 0x14,
            "physical layout": False,
            "show mesh": False
        },
        0: (
            368.0,
            136.0
        ),
        0x1: (
            340.0,
            40.0
        ),
        0x4: (
            420.0,
            180.0
        ),
        0x5: (
            560.0,
            200.0
        ),
        0x6: (
            100.0,
            180.0
        ),
        0x7: (
            420.0,
            220.0
        ),
        0x8: (
            560.0,
            240.0
        ),
        0x9: (
            260.0,
            200.0
        ),
        0xa: (
            100.0,
            240.0
        ),
        0xb: (
            260.0,
            260.0
        ),
        0xc: (
            100.0,
            280.0
        ),
        0xd: (
            240.0,
            300.0
        ),
        0xe: (
            420.0,
            260.0
        ),
        0xf: (
            560.0,
            280.0
        ),
        0x10: (
            560.0,
            320.0
        ),
        0x11: (
            560.0,
            360.0
        ),
        0x12: (
            420.0,
            300.0
        ),
        0x13: (
            100.0,
            320.0
        ),
        0x14: (
            100.0,
            360.0
        ),
        0x15: (
            420.0,
            400.0
        ),
        0x16: (
            420.0,
            440.0
        ),
        0x17: (
            100.0,
            400.0
        ),
        0x18: (
            100.0,
            440.0
        )
    },
    mtwl = {
        -1: {
            "columns width": {
                "#0": 0xa0,
                "id": 0x51,
                "offset": 0x62,
                "size": 0x98,
                "type": 0x141
            }
        },
        0x2: True
    },
    use_tabs = True
)

msp430x2xx_l0 = GUILayout(
    desc_name = "msp430x2xx",
    opaque = obj,
    shown = True
)
msp430x2xx_l0.lid = 0

project = GUIProject(
    layouts = [
        msp430_adc10_l0,
        msp430_adc12_l0,
        msp430_bcm_l0,
        msp430_comp_a_l0,
        msp430_dac12_l0,
        msp430_dma_l0,
        msp430_fmc_l0,
        msp430_ic_l0,
        msp430_io_l0,
        msp430_oa_l0,
        msp430_sd16_a_l0,
        msp430_svs_l0,
        msp430_timer_a_l0,
        msp430_timer_b_l0,
        msp430_usci_a_l0,
        msp430_usi_l0,
        msp430_wdt_l0,
        msp430x2xx_l0
    ],
    target_version = "v5.1.0",
    descriptions = [
        msp430x2xx,
        msp430_bcm,
        msp430_dma,
        msp430_ic,
        msp430_fmc,
        msp430_io,
        msp430_svs,
        msp430_wdt,
        msp430_timer_a,
        msp430_timer_b,
        msp430_usi,
        msp430_oa,
        msp430_comp_a,
        msp430_adc10,
        msp430_adc12,
        msp430_dac12,
        msp430_sd16_a,
        msp430_usci_a
    ]
)

