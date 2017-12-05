__all__ = [
    "MachineNode"
]

from .qom_desc import (
    DescriptionOf,
    QOMDescription
)
from itertools import count

from .qom import QOMPropertyTypeLink

from .machine import MachineType

from .machine_nodes import (
    SystemBusNode,
    SystemBusDeviceNode,
    DeviceNode,
    BusNode,
    IRQLine,
    IRQHub,
    MemoryNode
)

# machine model
class MultipleSystemBusesInMachine(RuntimeError):
    pass

class NodeHasId(RuntimeError):
    pass

class NodeIdIsAlreadyInUse(RuntimeError):
    pass

@DescriptionOf(MachineType)
class MachineNode(QOMDescription):
    def __description_init__(self):
        self.max_id = 0
        self.id2node = {}

        for n in self.devices + self.buses + self.irqs + self.mems + \
        self.irq_hubs:
            self.assign_id(n)

    def __dfs_children__(self):
        return QOMDescription.__dfs_children__(self) \
            + self.devices + self.buses + self.irqs + self.mems + self.irq_hubs

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field('name = "' + self.name + '"')
        gen.gen_field('directory = "' + self.directory + '"')
        if self.compat:
            for attr, val in self.compat.items():
                gen.gen_field(attr + " = ")
                gen.pprint(val)
        gen.gen_end()

        if not self.id2node:
            return

        # add nodes preserving id order to same identification
        pfx = gen.nameof(self) + ".add_node("
        for id, node in self.id2node.items():
            gen.line(pfx + gen.nameof(node) + ", with_id = " + str(id) + ")")

    def link(self, handle_system_bus = True):
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
                    if not irq in self.irqs:
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
                if not irq.src_dev in self.devices + self.irq_hubs:
                    self.add_node(irq.src[0])
                if not irq.dst_dev in self.devices + self.irq_hubs:
                    self.add_node(irq.dst[0])

            for mem in self.mems:
                if not (mem.parent is None or mem.parent in self.mems):
                    self.add_node(mem.parent)
                for child in mem.children:
                    if not child in self.mems:
                        self.add_node(child)

            for hub in self.irq_hubs:
                for irq in hub.irqs:
                    if not irq in self.irqs:
                        self.add_node(irq)

        if handle_system_bus:
            # A machine should have only one system bus
            sysbus = None

            # Find out system
            for bus in self.buses:
                if isinstance(bus, SystemBusNode):
                    if sysbus is None:
                        sysbus = bus
                    elif not sysbus == bus:
                        raise MultipleSystemBusesInMachine()

            # No system bus: create one
            if sysbus is None:
                sysbus = SystemBusNode()
                self.add_node(sysbus)

            # Attach all system bus devices to the system bus
            for dev in self.devices:
                if isinstance(dev, SystemBusDeviceNode):
                    if not dev.parent_bus:
                        dev.parent_bus = sysbus
                        sysbus.devices.append(dev)

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

    def add_node(self, n, with_id = None):
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

        if with_id is not None:
            if with_id in self.id2node.keys():
                raise NodeIdIsAlreadyInUse()
            if not n.id == -1:
                raise NodeHasId()

            n.id = with_id
            self.id2node[n.id] = n

            if with_id >= self.max_id:
                self.max_id = with_id + 1
        else:
            self.assign_id(n)

        self.added = True

    def assign_id(self, n):
        if not n.id == -1:
            raise NodeHasId()
        n.id = self.max_id
        self.max_id = self.max_id + 1

        self.id2node[n.id] = n

    def get_free_id(self):
        for i in count(0):
            if not i in self.id2node:
                return i
