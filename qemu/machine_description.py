import machine
from __builtin__ import isinstance
from source import Type
from project import QOMDescription

# properties
class QOMPropertyType(object):
    set_f = None
    build_val = None

class QOMPropertyTypeLink(QOMPropertyType):
    set_f = "object_property_set_link"

class QOMPropertyTypeString(QOMPropertyType):
    set_f = "object_property_set_str"

class QOMPropertyTypeBoolean(QOMPropertyType):
    set_f = "object_property_set_bool"

class QOMPropertyTypeInteger(QOMPropertyType):
    set_f = "object_property_set_int"

    @staticmethod
    def build_val(val):
        if Type.exists(val.prop_val):
            return str(val.prop_val)
        return "0x%0x" % val.prop_val

class QOMPropertyValue(object):
    def __init__(self,
        prop_type,
        prop_name,
        prop_val
        ):
        self.prop_type = prop_type
        self.prop_name = prop_name
        self.prop_val = prop_val

class Node(object):
    def __init__(self):
        self.id = -1

# bus models
class BusNode(Node):
    # Devices on bus with None C type will have NULL as bus parameter
    def __init__(self,
            parent = None,
            c_type = "BusState",
            cast = "BUS",
            child_name = "bus",
            force_index = True
            ):
        Node.__init__(self)

        self.c_type = c_type
        self.cast = cast
        self.parent_device = parent

        if parent is not None:
            parent.buses.append(self)

        self.devices = []
        self.child_name = child_name
        self.force_index = force_index

    def __children__(self):
        if self.parent_device is None:
            return []
        else:
            return [self.parent_device]

class SystemBusNode(BusNode):
    def __init__(self):
        # Assume, the system bus has no parent
        BusNode.__init__(self, parent = None)

class PCIExpressBusNode(BusNode):
    def __init__(self, host_bridge):
        BusNode.__init__(self,
            parent = host_bridge,
            c_type = "PCIBus",
            cast = "PCI_BUS",
            child_name = "pci"
            )

class ISABusNode(BusNode):
    def __init__(self, bus_controller):
        BusNode.__init__(self,
            parent = bus_controller,
            child_name = "isa"
            )

class IDEBusNode(BusNode):
    def __init__(self, bus_controller):
        BusNode.__init__(self,
            parent = bus_controller,
            child_name = "ide"
            )

class I2CBusNode(BusNode):
    def __init__(self, bus_controller):
        BusNode.__init__(self,
            parent = bus_controller,
            child_name = "i2c",
            cast = None,
            c_type = "I2CBus",
            force_index = False
            )

# IRQ line model

class IRQLine(Node):
    def __init__(self,
            src_dev,
            dst_dev,
            src_irq_idx = 0,
            dst_irq_idx = 0,
            src_irq_name = None,
            dst_irq_name = None
            ):
        Node.__init__(self)

        # src and dst are tuples (device, index)
        self.src = src_dev, src_irq_idx, src_irq_name
        self.dst = dst_dev, dst_irq_idx, dst_irq_name

        src_dev.irqs.append(self)
        dst_dev.irqs.append(self)

    def __children__(self):
        return [self.src[0], self.dst[0]]

class IRQHub(Node):
    def __init__(self, srcs, dsts):
        Node.__init__(self)

        self.srcs = list(srcs)
        self.dsts = list(dsts)

        for src in self.srcs:
            src[0].irqs.append(self)

        for dst in self.dsts:
            dst[0].irqs.append(self)

    def __children__(self):
        ret = []
        for src in self.srcs:
            ret.append(src[0])
        for dst in self.dsts:
            ret.append(dst[0])
        return ret

# QObject property model

class DevicePropertyDefinition(object):
    def __init__(self, property_name, property_type, property_value):
        self.property_name = self.property_name
        self.property_type = self.property_type
        self.property_value = self.property_value

# device models

class DeviceNode(Node):
    def __init__(self, qom_type, parent = None):
        Node.__init__(self)

        self.qom_type = qom_type
        self.parent_bus = parent

        if parent is not None:
            parent.devices.append(self)

        self.buses = []
        self.irqs = []
        self.properties = []

    def __children__(self):
        if self.parent_bus is None:
            ret = []
        else:
            ret = [self.parent_bus]

        for p in self.properties:
            if p.prop_type == QOMPropertyTypeLink:
                if p.prop_val is not None:
                    ret.append(p.prop_val)
        return ret

class SystemBusDeviceNode(DeviceNode):
    def __init__(self,
                 qom_type,
                 system_bus = None,
                 mmio = None,
                 pmio = None):
        DeviceNode.__init__(self, qom_type = qom_type, parent = system_bus)

        self.mmio_mappings = []
        self.pmio_mappings = []

        if mmio is not None :
            for index, address in enumerate(mmio):
                self.add_memory_mapping(address, index)

        if pmio is not None :
            for index, port in enumerate(pmio):
                self.add_port_mapping(port, index)

    def add_memory_mapping(self, address, index = 0):
        l = len(self.mmio_mappings)
        if l <= index:
            for i in xrange(l, index + 1):
                self.mmio_mappings.append(None)

        self.mmio_mappings[index] = address

    def delete_memory_mapping(self, index = 0):
        if index < len(self.mmio_mappings):
            self.mmio_mappings[index] = None
        # TODO: truncate last None items in the array

    def add_port_mapping(self, port, index = 0):
        l = len(self.mmio_mappings)
        if l <= index:
            for i in xrange(l, index + 1):
                self.pmio_mappings.append(None)

        self.pmio_mappings[index] = port

    def delete_port_mapping(self, index = 0):
        if index < len(self.pmio_mappings):
            self.pmio_mappings[index] = None
        # TODO: truncate last None items in the array

class PCIExpressDeviceNode(DeviceNode):
    def __init__(self, 
                 qom_type,
                 pci_express_bus,
                 slot,
                 function,
                 multifunction = False):
        DeviceNode.__init__(
            self, 
            qom_type = qom_type,
            parent = pci_express_bus
            )

        self.slot = slot
        self.function = function
        self.multifunction = multifunction

# Memory tree model

class MemoryNodeAlreadyHasParent(Exception):
    pass

class MemoryNodeCannotHasChildren(Exception):
    pass

class MemoryNode(Node):
    def __init__(self, 
            name,
            size,
            ):
        Node.__init__(self)

        self.name = name
        self.size = size

        self.parent = None
        self.offset = 0
        self.may_overlap = True
        self.priority = 1

        self.children = []

        self.alias_to = None
        self.alias_offset = 0

    def __children__(self):
        if self.alias_to is not None:
            return [self.alias_to]
        return [] if self.parent is None else [self.parent]

    def add_child(self, child, offset = 0, may_overlap = True, priority = 1):
        if child.parent is not None:
            raise MemoryNodeAlreadyHasParent()

        child.offset = offset
        child.may_overlap = may_overlap
        child.priority = priority
        child.parent = self
        self.children.append(child)

class MemoryLeafNode(MemoryNode):
    def __init__(self, 
        name,
        size,
        ):
        MemoryNode.__init__(self, name = name, size = size)
    
    def add_child(self, child, offset = 0, may_overlap = True, priority = 1):
        raise MemoryNodeCannotHasChildren()

class MemoryAliasNode(MemoryLeafNode):
    def __init__(self, name, size, alias_to, offset = 0):
        MemoryLeafNode.__init__(self, name = name, size = size)
        self.alias_to = alias_to
        self.alias_offset = offset

class MemoryRAMNode(MemoryLeafNode):
    def __init__(self, name, size):
        MemoryLeafNode.__init__(self, name = name, size = size)

class MemoryROMNode(MemoryLeafNode):
    def __init__(self, name, size):
        MemoryLeafNode.__init__(self, name = name, size = size)

# machine model
class MultipleSystemBusesInMachine(Exception):
    pass

class NodeHasId(Exception):
    pass

class MachineNode(QOMDescription):
    def __init__(self,
        name,
        directory,
        devices = None,
        buses = None,
        irqs = None,
        mems = None,
        irq_hubs = None
    ):
        QOMDescription.__init__(self, name = name, directory = directory)

        self.max_id = 0
        self.devices = [] if devices is None else list(devices)
        self.buses = [] if buses is None else list(buses)
        self.irqs = [] if irqs is None else list(irqs)
        self.mems = [] if mems is None else list(mems)
        self.irq_hubs = [] if irq_hubs is None else list(irq_hubs)

        self.id2node = {}

        for n in self.devices + self.buses + self.irqs + self.mems + self.irq_hubs:
            self.assign_id(n)

        self.link()

    def link(self):
        self.added = True

        # Travel throw all trees, incrementally adding nodes to machine arrays
        while self.added:
            self.added = False
            for dev in self.devices:
                if not (dev.parent_bus is None or dev.parent_bus in self.buses):
                        self.add_node(dev.parent_bus)
                for bus in dev.buses:
                    if not bus in self.buses:
                        self.add_node(bus)
                for irq in dev.irqs:
                    if not irq in self.irqs and not irq in self.irq_hubs:
                        self.add_node(irq)
                for prop in dev.properties:
                    if prop.prop_type == QOMPropertyTypeLink:
                        if prop.prop_val and not self.has_node(prop.prop_val):
                            self.add_node(prop.prop_val)

            for bus in self.buses:
                if not (   bus.parent_device is None
                        or bus.parent_device in self.devices):
                    self.add_node(bus.parent_device)
                for dev in bus.devices:
                    if not dev in self.devices:
                        self.add_node(dev)

            for irq in self.irqs:
                if not irq.src[0] in self.devices:
                    self.add_node(irq.src[0])
                if not irq.dst[0] in self.devices:
                    self.add_node(irq.dst[0])

            for mem in self.mems:
                if not (mem.parent is None or mem.parent in self.mems):
                    self.add_node(mem.parent)
                for child in mem.children:
                    if not child in self.mems:
                        self.add_node(child)

            for hub in self.irq_hubs:
                for dev in [ x[0] for x in (hub.srcs + hub.dsts) ]:
                    if not dev in self.devices:
                        self.add_node(dev)

        # A machine should have only one system bus
        self.sysbus = None

        # Find out system
        for bus in self.buses:
            if isinstance(bus, SystemBusNode):
                if self.sysbus is None:
                    self.sysbus = bus
                elif not self.sysbus == bus:
                    raise MultipleSystemBusesInMachine()

        # No system bus: create one
        if self.sysbus == None:
            self.sysbus = SystemBusNode()
            self.add_node(self.sysbus)

        # Attach all system bus devices to the system bus
        for dev in self.devices:
            if isinstance(dev, SystemBusDeviceNode):
                if not dev.parent_bus:
                    dev.parent_bus = self.sysbus
                    self.sysbus.devices.append(dev)

    def has_node(self, n):
        if isinstance(n, DeviceNode):
            return n in self.devices
        elif isinstance(n, BusNode):
            return n in self.buses
        elif isinstance(n, IRQLine):
            return n in self.irqs
        elif isinstance(n, MemoryNode):
            return n in self.mems
        elif isinstance(n, IRQHub):
            return n in self.irq_hubs
        else:
            return False

    def add_node(self, n):
        if isinstance(n, DeviceNode):
            self.devices.append(n)
        elif isinstance(n, BusNode):
            self.buses.append(n)
        elif isinstance(n, IRQLine):
            self.irqs.append(n)
        elif isinstance(n, MemoryNode):
            self.mems.append(n)
        elif isinstance(n, IRQHub):
            self.irq_hubs.append(n)
        else:
            return

        self.assign_id(n)

        self.added = True

    def assign_id(self, n):
        if not n.id == -1:
            raise NodeHasId()
        n.id = self.max_id
        self.max_id = self.max_id + 1

        self.id2node[n.id] = n

    def gen_type(self):
        return machine.MachineType(
            machine = self
            )