__all__ = [
    # Machine nodes
    "Node",
        "BusNode",
            "SystemBusNode",
            "PCIExpressBusNode",
            "ISABusNode",
            "IDEBusNode",
            "I2CBusNode",
        "IRQLine",
        "IRQHub",
        "DeviceNode",
            "SystemBusDeviceNode",
            "PCIExpressDeviceNode",
        "MemoryNode",
            "MemoryLeafNode",
                "MemoryAliasNode",
                "MemoryRAMNode",
                "MemoryROMNode",
    # Exceptions
    "MemoryNodeHasNoSuchParent"
]

from itertools import \
    count

from six.moves import \
    range as xrange

from .qom import \
    QOMPropertyTypeLink

from bisect import \
    insort

class Node(object):
    def __init__(self, var_base = None):
        self.id = -1
        if var_base is None:
            raise NotImplementedError("No default base for variable name")
        self.var_base = var_base

# bus models
class BusNode(Node):
    # Devices on bus with None C type will have NULL as bus parameter
    def __init__(self,
        parent = None,
        c_type = "BusState",
        cast = "BUS",
        child_name = "bus",
        force_index = True,
        var_base = "bus",
        **kw
    ):
        Node.__init__(self, var_base = var_base, **kw)

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

    def gen_child_name_for_bus(self):
        if self.parent_device is None \
        or len(self.parent_device.buses) == 1 and not self.force_index:
            return self.child_name
        else:
            return "%s.%u" % (
                self.child_name, self.parent_device.buses.index(self)
            )

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        if self.parent_device:
            gen.gen_field("parent = " + gen.nameof(self.parent_device))
        if not self.c_type == "BusState":
            gen.gen_field('c_type = ' + gen.gen_const(self.c_type))
        if not self.cast == "BUS":
            gen.gen_field('cast = ' + gen.gen_const(self.cast))
        if not self.child_name == "bus":
            gen.gen_field('child_name = ' + gen.gen_const(self.child_name))
        if not self.force_index:
            gen.gen_field("force_index = False")
        gen.gen_end()

    def __get_init_arg_val__(self, arg_name):
        if arg_name == "parent":
            arg_name = "parent_device"
        return getattr(self, arg_name)

class SystemBusNode(BusNode):
    def __init__(self, **kw):
        # Assume, the system bus has no parent
        BusNode.__init__(self, parent = None, **kw)

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_end()
        if self.parent_device:
            # Note that a system bus cannot have parent device by design. But,
            # if user really want problems with code generator then it is
            # technically possible.
            gen.line(gen.nameof(self.parent_device) + ".append_child_bus("
                + gen.nameof(self) + ")"
            )

class PCIExpressBusNode(BusNode):
    def __init__(self, host_bridge,
        c_type = "PCIBus",
        cast = "PCI_BUS",
        child_name = "pci",
        **kw
    ):
        BusNode.__init__(self,
            parent = host_bridge,
            c_type = c_type,
            cast = cast,
            child_name = child_name,
            **kw
        )

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field("host_bridge = " + gen.nameof(self.parent_device))
        gen.gen_end()

    def __get_init_arg_val__(self, arg_name):
        if arg_name == "host_bridge":
            arg_name = "parent_device"
        return getattr(self, arg_name)

class ISABusNode(BusNode):
    def __init__(self, bus_controller, child_name = "isa", **kw):
        BusNode.__init__(self,
            parent = bus_controller,
            child_name = child_name,
            **kw
        )

    def __get_init_arg_val__(self, arg_name):
        if arg_name == "bus_controller":
            arg_name = "parent_device"
        return getattr(self, arg_name)

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field("bus_controller = " + gen.nameof(self.parent_device))
        gen.gen_end()

class IDEBusNode(BusNode):
    def __init__(self, bus_controller, child_name = "ide", **kw):
        BusNode.__init__(self,
            parent = bus_controller,
            child_name = child_name,
            **kw
        )

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field("bus_controller = " + gen.nameof(self.parent_device))
        gen.gen_end()

    def __get_init_arg_val__(self, arg_name):
        if arg_name == "bus_controller":
            arg_name = "parent_device"
        return getattr(self, arg_name)

class I2CBusNode(BusNode):
    def __init__(self, bus_controller,
        child_name = "i2c",
        cast = None,
        c_type = "I2CBus",
        force_index = False,
        **kw
    ):
        BusNode.__init__(self,
            parent = bus_controller,
            child_name = child_name,
            cast = cast,
            c_type = c_type,
            force_index = force_index,
            **kw
        )

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field("bus_controller = " + gen.nameof(self.parent_device))
        gen.gen_end()

    def __get_init_arg_val__(self, arg_name):
        if arg_name == "bus_controller":
            arg_name = "parent_device"
        return getattr(self, arg_name)

# IRQ line model

class IRQLine(Node):
    def __init__(self, src_dev, dst_dev,
        src_irq_idx = 0,
        dst_irq_idx = 0,
        src_irq_name = None,
        dst_irq_name = None,
        var_base = "irq",
        **kw
    ):
        Node.__init__(self, var_base = var_base, **kw)

        # source node (device or hub)
        self.src_dev = src_dev
        self.src_irq_idx = src_irq_idx # GPIO index
        self.src_irq_name = src_irq_name # GPIO name

        # destination node
        self.dst_dev = dst_dev
        self.dst_irq_idx = dst_irq_idx
        self.dst_irq_name = dst_irq_name

        src_dev.irqs.append(self)
        dst_dev.irqs.append(self)

    @property
    def src(self):
        return (self.src_dev, self.src_irq_idx, self.src_irq_name)

    @property
    def dst(self):
        return (self.dst_dev, self.dst_irq_idx, self.dst_irq_name)

    @property
    def src_node(self):
        return self.src_dev

    @src_node.setter
    def src_node(self, value):
        self.src_dev.irqs.remove(self)
        self.src_dev = value
        value.irqs.append(self)

    @property
    def dst_node(self):
        return self.dst_dev

    @dst_node.setter
    def dst_node(self, value):
        self.dst_dev.irqs.remove(self)
        self.dst_dev = value
        value.irqs.append(self)

    @property
    def src_index(self):
        return self.src_irq_idx

    @src_index.setter
    def src_index(self, value):
        self.src_irq_idx = value

    @property
    def dst_index(self):
        return self.dst_irq_idx

    @dst_index.setter
    def dst_index(self, value):
        self.dst_irq_idx = value

    @property
    def src_name(self):
        return self.src_irq_name

    @src_name.setter
    def src_name(self, value):
        self.src_irq_name = value

    @property
    def dst_name(self):
        return self.dst_irq_name

    @dst_name.setter
    def dst_name(self, value):
        self.dst_irq_name = value

    def hub_ended(self):
        return    isinstance(self.src_dev, IRQHub) \
               or isinstance(self.dst_dev, IRQHub)

    def __children__(self):
        return [ self.src_dev, self.dst_dev ]

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field("src_dev = " + gen.nameof(self.src_dev))
        gen.gen_field("dst_dev = " + gen.nameof(self.dst_dev))
        if self.src_irq_idx != 0:
            gen.gen_field("src_irq_idx = " + gen.gen_const(self.src_irq_idx))
        if self.dst_irq_idx != 0:
            gen.gen_field("dst_irq_idx = " + gen.gen_const(self.dst_irq_idx))
        if self.src_irq_name:
            gen.gen_field('src_irq_name = ' + gen.gen_const(self.src_irq_name))
        if self.dst_irq_name:
            gen.gen_field('dst_irq_name = ' + gen.gen_const(self.dst_irq_name))
        gen.gen_end()

class IRQHub(Node):
    def __init__(self, srcs = None, dsts = None, var_base = "irq", **kw):
        Node.__init__(self, var_base = var_base, **kw)

        self.irqs = []

        if srcs:
            for end in srcs:
                IRQLine(
                    end[0], self,
                    src_irq_idx = end[1], dst_irq_idx = 0,
                    src_irq_name = end[2], dst_irq_name = None
                )

        if dsts:
            for end in dsts:
                IRQLine(
                    self, end[0],
                    src_irq_idx = 0, dst_irq_idx = end[1],
                    src_irq_name = None, dst_irq_name = end[2]
                )

    def __children__(self):
        referenced_hubs = []
        for line in self.irqs:
            dst = line.dst_node
            if dst is self:
                continue
            if isinstance(dst, IRQHub):
                referenced_hubs.append(dst)

        return sorted(referenced_hubs, key = lambda h : h.id)

    def __get_init_arg_val__(self, arg_name):
        """ This method alwaus returns [] (empty list) for `srcs` and `dsts`
        arguments because of next reasons.
        - During backing a hub up for a reversible operation they are always
        empty by reversible operation mechanism design.
        - During loading a hub from a Python script they will be rebuilt by
        instantiation of corresponding `IRQLine` objects. So, they must be
        empty preventing IRQ line duplication.
        - Older versions of the tool assume they are positional arguments and
        never `None`-valued. So, they must present and be exactly empty lists.
        """
        if arg_name in ["srcs", "dsts"]:
            return []
        return getattr(self, arg_name)

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        # Sources and destinations will be set during loading of
        # corresponding IRQ lines.
        gen.write("srcs = [], dsts = []")
        gen.gen_end()

# QObject property model

class DevicePropertyDefinition(object):
    def __init__(self, property_name, property_type, property_value):
        self.property_name = self.property_name
        self.property_type = self.property_type
        self.property_value = self.property_value

# device models

class PropList(dict):
    def __init__(self, original = None, *args, **kw):
        dict.__init__(original if original else {}, *args, **kw)
        self.__names = []

    def append(self, prop):
        # It is defined that a property descriptor have property name.
        # Hence the key for a property in dict could be got automatically.
        self[prop.prop_name] = prop

    def __setitem__(self, name, prop):
        if name not in self:
            insort(self.__names, name)
        return dict.__setitem__(self, name, prop)

    def extend(self, props):
        for prop in props:
            self.append(prop)

    def keys(self):
        return self.__names.__iter__()

    def __iter__(self):
        return self.__iterator()

    def __iterator(self):
        for name in self.keys():
            yield self[name]

    def __delitem__(self, name):
        self.__names.remove(name)
        return dict.__delitem__(self, name)

class DeviceNode(Node):
    def __init__(self, qom_type, parent = None, var_base = "dev", **kw):
        Node.__init__(self, var_base = var_base, **kw)

        self.qom_type = qom_type
        self.parent_bus = parent

        if parent is not None:
            parent.devices.append(self)

        self.buses = []
        self.irqs = []
        # Using a dict for properties simplifies looking for the property
        # descriptor by its property name
        self.properties = PropList()

    # Internal use only.
    def append_child_bus(self, bus):
        if bus.parent_device is not None:
            raise Exception("The bus already have a parent.")
        bus.parent_device = self
        self.buses.append(bus)

    def gen_prop_val(self, gen, p):
        if p.prop_type == QOMPropertyTypeLink:
            if p.prop_val:
                return gen.nameof(p.prop_val)
            else:
                return "None"
        else:
            return gen.gen_const(p.prop_val)

    def gen_props(self, gen):
        if not self.properties:
            return

        gen.reset_gen_common(gen.nameof(self) + ".properties.extend([")
        for p in self.properties:
            gen.gen_field(
                "QOMPropertyValue(" + p.prop_type.__name__
                + ', ' + gen.gen_const(p.prop_name)
                + ', ' + self.gen_prop_val(gen, p)
                + ")"
            )
        gen.gen_end(suffix = "])")

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field('qom_type = ' + gen.gen_const(self.qom_type))
        if self.parent_bus:
            gen.gen_field("parent = " + gen.nameof(self.parent_bus))
        gen.gen_end()
        self.gen_props(gen)

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

    def __get_init_arg_val__(self, arg_name):
        if arg_name == "parent":
            arg_name = "parent_bus"
        return getattr(self, arg_name)

def iter_mappings(mapping):
    for idx in xrange(0, max(mapping.keys()) + 1):
        try:
            yield mapping[idx]
        except KeyError:
            yield None

class SystemBusDeviceNode(DeviceNode):
    def __init__(self, qom_type,
        system_bus = None,
        mmio = None,
        pmio = None,
        **kw
    ):
        DeviceNode.__init__(self,
            qom_type = qom_type,
            parent = system_bus,
            **kw
        )

        self.mmio_mappings = {}
        self.pmio_mappings = {}

        if mmio is not None :
            for index, address in enumerate(mmio):
                self.add_memory_mapping(address, index)

        if pmio is not None :
            for index, port in enumerate(pmio):
                self.add_port_mapping(port, index)

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field('qom_type = ' + gen.gen_const(self.qom_type))
        if self.parent_bus:
            gen.gen_field("system_bus = " + gen.nameof(self.parent_bus))

        if self.mmio_mappings:
            gen.gen_field("mmio = ")
            gen.pprint(list(iter_mappings(self.mmio_mappings)))

        if self.pmio_mappings:
            gen.gen_field("pmio = ")
            gen.pprint(list(iter_mappings(self.pmio_mappings)))

        gen.gen_end()
        self.gen_props(gen)

    def add_memory_mapping(self, address, index = 0):
        """ Adds MMIO at first empty slot starting from index """
        for idx in count(index):
            if not idx in self.mmio_mappings:
                break

        self.mmio_mappings[idx] = address

    def delete_memory_mapping(self, index = 0):
        del self.mmio_mappings[index]

    def add_port_mapping(self, port, index = 0):
        """ Adds PMIO at first empty slot starting from index """
        for idx in count(index):
            if not idx in self.pmio_mappings:
                break

        self.pmio_mappings[idx] = port

    def delete_port_mapping(self, index = 0):
        del self.pmio_mappings[index]

    def __get_init_arg_val__(self, arg_name):
        if arg_name == "system_bus":
            arg_name = "parent_bus"
        elif arg_name == "mmio":
            if self.mmio_mappings:
                return list(iter_mappings(self.mmio_mappings))
            else:
                return None
        elif arg_name == "pmio":
            if self.pmio_mappings:
                return list(iter_mappings(self.pmio_mappings))
            else:
                return None
        return getattr(self, arg_name)

class PCIExpressDeviceNode(DeviceNode):
    def __init__(self, qom_type, pci_express_bus, slot, function,
        multifunction = False,
        **kw
    ):
        DeviceNode.__init__(self,
            qom_type = qom_type,
            parent = pci_express_bus,
            **kw
        )

        self.slot = slot
        self.function = function
        self.multifunction = multifunction

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field('qom_type = ' + gen.gen_const(self.qom_type))
        gen.gen_field("pci_express_bus = " + gen.nameof(self.parent_bus))
        gen.gen_field("slot = " + gen.gen_const(self.slot))
        gen.gen_field("function = " + gen.gen_const(self.function))
        if self.multifunction:
            gen.gen_field("multifunction = True")
        gen.gen_end()
        self.gen_props(gen)

    def __get_init_arg_val__(self, arg_name):
        if arg_name == "pci_express_bus":
            arg_name = "parent_bus"
        return getattr(self, arg_name)

# Memory tree model

class MemoryNodeAlreadyHasParent(Exception):
    pass

class MemoryNodeCannotHasChildren(Exception):
    pass

class MemoryNodeHasNoSuchParent(Exception):
    pass

class MemoryNode(Node):
    def __init__(self, name, size, var_base = "mem", **kw):
        Node.__init__(self, var_base = var_base, **kw)

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

    def remove_child(self, child):
        if not child.parent is self:
            raise MemoryNodeHasNoSuchParent()

        child.parent = None
        self.children.remove(child)

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field('name = ' + gen.gen_const(self.name))
        gen.gen_field("size = " + gen.gen_const(self.size))
        gen.gen_end()
        self.gen_parent_attachment(gen)

    def gen_parent_attachment(self, gen):
        if self.parent:
            gen.reset_gen_common(gen.nameof(self.parent) + ".add_child(")
            gen.gen_field("child = " + gen.nameof(self))
            if self.offset != 0:
                gen.gen_field("offset = " + gen.gen_const(self.offset))
            if not self.may_overlap:
                gen.gen_field("may_overlap = False")
            if self.priority != 0:
                gen.gen_field("priority = " + gen.gen_const(self.priority))
            gen.gen_end()

class MemoryLeafNode(MemoryNode):
    def add_child(self, child, offset = 0, may_overlap = True, priority = 1):
        raise MemoryNodeCannotHasChildren()

class MemoryAliasNode(MemoryLeafNode):
    def __init__(self, name, size, alias_to, offset = 0, **kw):
        MemoryLeafNode.__init__(self, name, size, **kw)

        self.alias_to = alias_to
        self.alias_offset = offset

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field('name = ' + gen.gen_const(self.name))
        gen.gen_field("size = " + gen.gen_const(self.size))
        gen.gen_field("alias_to = " + gen.nameof(self.alias_to))
        gen.gen_field("offset = " + gen.gen_const(self.alias_offset))
        gen.gen_end()

        self.gen_parent_attachment(gen)

    def __get_init_arg_val__(self, arg_name):
        if arg_name == "offset":
            arg_name = "alias_offset"
        return getattr(self, arg_name)

class MemoryRAMNode(MemoryLeafNode):
    pass

class MemoryROMNode(MemoryLeafNode):
    pass
