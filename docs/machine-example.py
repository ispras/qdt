obj0 = SystemBusNode()

obj1 = SystemBusDeviceNode(
    qom_type = "TYPE_INTERRUPT_CONTROLLER",
    system_bus = obj0,
    var_base = "interrupt_controller"
)

obj2 = SystemBusDeviceNode(
    qom_type = "TYPE_UART",
    system_bus = obj0,
    var_base = "uart"
)

obj3 = DeviceNode(
    qom_type = "TYPE_CPU",
    var_base = "cpu"
)

obj4 = SystemBusDeviceNode(
    qom_type = "UART",
    system_bus = obj0,
    var_base = "uart"
)

obj5 = SystemBusDeviceNode(
    qom_type = "TYPE_PCI_HOST",
    system_bus = obj0,
    var_base = "pci_host"
)

obj6 = PCIExpressBusNode(
    host_bridge = obj5
)

obj7 = PCIExpressDeviceNode(
    qom_type = "TYPE_ETHERNET",
    pci_express_bus = obj6,
    slot = 0,
    function = 0,
    var_base = "ethernet"
)

obj8 = PCIExpressDeviceNode(
    qom_type = "TYPE_ETHERNET",
    pci_express_bus = obj6,
    slot = 0,
    function = 0,
    var_base = "ethernet"
)

obj9 = SystemBusDeviceNode(
    qom_type = "TYPE_ROM",
    system_bus = obj0,
    var_base = "rom"
)

obj10 = SystemBusDeviceNode(
    qom_type = "TYPE_HID",
    system_bus = obj0,
    var_base = "hid"
)

obj11 = SystemBusDeviceNode(
    qom_type = "TYPE_DISPLAY",
    system_bus = obj0,
    var_base = "display"
)

obj12 = IRQLine(
    src_dev = obj1,
    dst_dev = obj3
)

obj13 = IRQHub(
    srcs = [],
    dsts = []
)

obj14 = IRQLine(
    src_dev = obj13,
    dst_dev = obj1
)

obj15 = IRQLine(
    src_dev = obj2,
    dst_dev = obj13
)

obj16 = IRQLine(
    src_dev = obj4,
    dst_dev = obj13
)

obj17 = IRQLine(
    src_dev = obj5,
    dst_dev = obj1,
    dst_irq_idx = 0x1
)

obj18 = IRQLine(
    src_dev = obj9,
    dst_dev = obj1,
    dst_irq_idx = 0x2
)

obj19 = IRQLine(
    src_dev = obj11,
    dst_dev = obj1,
    dst_irq_idx = 0x3
)

obj20 = IRQLine(
    src_dev = obj10,
    dst_dev = obj1,
    dst_irq_idx = 0x4
)

obj21 = MachineNode(
    name = "description0",
    directory = ""
)
obj21.add_node(obj0, with_id = 0)
obj21.add_node(obj1, with_id = 1)
obj21.add_node(obj2, with_id = 2)
obj21.add_node(obj13, with_id = 3)
obj21.add_node(obj3, with_id = 4)
obj21.add_node(obj12, with_id = 5)
obj21.add_node(obj14, with_id = 6)
obj21.add_node(obj4, with_id = 7)
obj21.add_node(obj15, with_id = 8)
obj21.add_node(obj16, with_id = 9)
obj21.add_node(obj5, with_id = 10)
obj21.add_node(obj6, with_id = 11)
obj21.add_node(obj7, with_id = 12)
obj21.add_node(obj8, with_id = 13)
obj21.add_node(obj17, with_id = 14)
obj21.add_node(obj9, with_id = 15)
obj21.add_node(obj18, with_id = 16)
obj21.add_node(obj10, with_id = 17)
obj21.add_node(obj11, with_id = 18)
obj21.add_node(obj19, with_id = 19)
obj21.add_node(obj20, with_id = 20)

obj22 = MachineWidgetLayout(
    mdwl = {
        0: (
            41.20573293511035,
            125.9760158583141
        ),
        0x1: (
            96.1447438641203,
            96.92583042837722
        ),
        0x2: (
            84.0,
            189.0
        ),
        0x3: (
            148.0,
            157.0
        ),
        0x4: (
            201.0,
            34.0
        ),
        0x7: (
            154.0,
            217.0
        ),
        0xa: (
            273.0,
            241.0
        ),
        0xb: (
            293.0,
            142.0
        ),
        0xc: (
            334.0,
            55.0
        ),
        0xd: (
            333.0,
            98.0
        ),
        0xf: (
            112.0,
            26.0
        ),
        0x11: (
            -7.0,
            16.0
        ),
        0x12: (
            -39.0,
            60.0
        ),
        -1: {
            "physical layout": False,
            "IRQ lines points": {
                0x10: [],
                0x13: [],
                0x14: [],
                0x5: [],
                0x6: [],
                0x8: [],
                0x9: [],
                0xe: [
                    (
                        230.0,
                        210.0
                    ),
                    (
                        229.0,
                        165.0
                    )
                ]
            },
            "show mesh": False,
            "mesh step": 0x14
        }
    },
    mtwl = {},
    use_tabs = True
)

obj23 = GUILayout(
    desc_name = "description0",
    opaque = obj22,
    shown = True
)
obj23.lid = 0

obj24 = GUIProject(
    layouts = [
        obj23
    ],
    build_path = None,
    descriptions = [
        obj21
    ]
)

