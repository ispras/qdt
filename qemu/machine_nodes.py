__all__ = [
    # Machine nodes
    "Node"
      , "BusNode"
          , "SystemBusNode"
          , "PCIExpressBusNode"
          , "ISABusNode"
          , "IDEBusNode"
          , "I2CBusNode"
      , "IRQLine"
      , "IRQHub"
      , "DeviceNode"
          , "SystemBusDeviceNode"
          , "PCIExpressDeviceNode"
      , "MemoryNode"
          , "MemorySASNode"
          , "MemoryLeafNode"
              , "MemoryAliasNode"
              , "MemoryRAMNode"
              , "MemoryROMNode"
    # Exceptions
  , "MemoryNodeHasNoSuchParent"
  , "MemorySASNodeCanNotHaveParent"
]

from itertools import (
    count
)
from six.moves import (
    zip_longest,
    range as xrange
)
from .qom import (
    idon,
    QOMPropertyTypeLink
)
from bisect import (
    insort
)
from source import (
    CSTR,
    CINT
)


class Node(object):
    def __init__(self, var_base = None):
        self.id = -1
        if var_base is None:
            raise NotImplementedError("No default base for variable name")
        self.var_base = var_base

    def __var_base__(self):
        return self.var_base

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_args(self, pa_names = True)
        gen.gen_end()

    def __eq__(self, o):
        if type(self) is not type(o):
            return False
        if self.id != o.id:
            return False
        if self.var_base != o.var_base:
            return False
        return True

    __ne__ = lambda self, *a : not self.__eq__(*a)
    __hash__ = object.__hash__


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

    def __dfs_children__(self):
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

    def __get_init_arg_val__(self, arg_name):
        if arg_name == "parent":
            arg_name = "parent_device"
        return getattr(self, arg_name)

    def __eq__(self, o):
        if not Node.__eq__(self, o):
            return False

        if idon(self.parent_device) != idon(o.parent_device):
            return False
        for a in ("c_type", "cast", "child_name", "force_index"):
            if getattr(self, a) != getattr(o, a):
                return False

        sdevs = set(d.id for d in self.devices)
        odevs = set(d.id for d in o.devices)

        if sdevs ^ odevs:
            return False
        return True


class SystemBusNode(BusNode):
    def __init__(self, **kw):
        # Assume, the system bus has no parent
        BusNode.__init__(self, parent = None, **kw)

    def __gen_code__(self, gen):
        super(SystemBusNode, self).__gen_code__(gen)
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
        var_base = "pci",
        **kw
    ):
        BusNode.__init__(self,
            parent = host_bridge,
            c_type = c_type,
            cast = cast,
            child_name = child_name,
            var_base = var_base,
            **kw
        )

    def __get_init_arg_val__(self, arg_name):
        if arg_name == "host_bridge":
            arg_name = "parent_device"
        return getattr(self, arg_name)

class ISABusNode(BusNode):
    def __init__(self, bus_controller,
        child_name = "isa",
        var_base = "isa",
        **kw
    ):
        BusNode.__init__(self,
            parent = bus_controller,
            child_name = child_name,
            var_base = var_base,
            **kw
        )

    def __get_init_arg_val__(self, arg_name):
        if arg_name == "bus_controller":
            arg_name = "parent_device"
        return getattr(self, arg_name)

class IDEBusNode(BusNode):
    def __init__(self,
            bus_controller,
            child_name = "ide",
            var_base = "ide",
            **kw
        ):
        BusNode.__init__(self,
            parent = bus_controller,
            child_name = child_name,
            var_base = var_base,
            **kw
        )

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
        var_base = "i2c",
        **kw
    ):
        BusNode.__init__(self,
            parent = bus_controller,
            child_name = child_name,
            cast = cast,
            c_type = c_type,
            force_index = force_index,
            var_base = var_base,
            **kw
        )

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

    def hub_ended(self):
        return    isinstance(self.src_dev, IRQHub) \
               or isinstance(self.dst_dev, IRQHub)

    def __dfs_children__(self):
        return [ self.src_dev, self.dst_dev ]

    def __eq__(self, o):
        if not Node.__eq__(self, o):
            return False
        # Neither source nor destination device can be None.
        if self.src_dev.id != o.src_dev.id:
            return False
        if self.dst_dev.id != o.dst_dev.id:
            return False

        for a in ("src_irq_idx", "src_irq_name", "dst_irq_idx", "dst_irq_name"
        ):
            if getattr(self, a) != getattr(o, a):
                return False
        return True


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

    def __dfs_children__(self):
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

    def __eq__(self, o):
        if not Node.__eq__(self, o):
            return False
        # IRQ order is not significant
        sirqs = set(i.id for i in self.irqs)
        oirqs = set(i.id for i in o.irqs)

        if sirqs ^ oirqs:
            return False
        return True

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
        super(DeviceNode, self).__gen_code__(gen)
        self.gen_props(gen)

    def __dfs_children__(self):
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

    def __eq__(self, o):
        if not Node.__eq__(self, o):
            return False
        if self.qom_type != o.qom_type:
            return False
        if idon(self.parent_bus) != idon(o.parent_bus):
            return False
        if self.properties != o.properties:
            return False
        # order of buses is significant
        if len(self.buses) != len(o.buses):
            return False
        for sb, ob in zip(self.buses, o.buses):
            if sb.id != ob.id:
                return False
        # order of IRQs is not significant
        sirqs = set(i.id for i in self.irqs)
        oirqs = set(i.id for i in o.irqs)

        if sirqs ^ oirqs:
            return False
        return True


def iter_mappings(mapping):
    if not mapping:
        # empty mapping, nothing to iterate
        return
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

    def __eq__(self, o):
        if not DeviceNode.__eq__(self, o):
            return False

        # Order of mapping is significant including holes (None) between
        # mappings.
        for mapping in ["mmio_mappings", "pmio_mappings"]:
            for sm, om in zip_longest(
                iter_mappings(getattr(self, mapping)),
                iter_mappings(getattr(o, mapping))
            ):
                if sm != om:
                    return False
        return True


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

    def __get_init_arg_val__(self, arg_name):
        if arg_name == "pci_express_bus":
            arg_name = "parent_bus"
        return getattr(self, arg_name)

    def __eq__(self, o):
        if not DeviceNode.__eq__(self, o):
            return False
        for a in ("slot", "function", "multifunction"):
            if getattr(self, a) != getattr(o, a):
                return False
        return True

# Memory tree model

class MemoryNodeAlreadyHasParent(Exception):
    pass

class MemoryNodeCannotHasChildren(Exception):
    pass

class MemoryNodeHasNoSuchParent(Exception):
    pass

class MemorySASNodeCanNotHaveParent(Exception):
    pass

class MemoryNode(Node):
    def __init__(self, name, size, var_base = "mem", **kw):
        Node.__init__(self, var_base = var_base, **kw)

        self.name = CSTR(name)
        self.size = None if size is None else CINT(size)

        self.parent = None
        self.offset = CINT(0, base = 16)
        self.may_overlap = True
        self.priority = CINT(1)

        self.children = []

        self.alias_to = None
        self.alias_offset = CINT(0, base = 16)

    def __dfs_children__(self):
        if self.alias_to is not None:
            return [self.alias_to]
        return [] if self.parent is None else [self.parent]

    def add_child(self, child, offset = 0, may_overlap = True, priority = 1):
        if child.parent is not None:
            raise MemoryNodeAlreadyHasParent()

        if isinstance(child, MemorySASNode):
            raise MemorySASNodeCanNotHaveParent()

        child.offset.set(offset)
        child.may_overlap = may_overlap
        child.priority.set(priority)
        child.parent = self
        self.children.append(child)

    def remove_child(self, child):
        if not child.parent is self:
            raise MemoryNodeHasNoSuchParent()

        child.parent = None
        self.children.remove(child)

    def __gen_code__(self, gen):
        super(MemoryNode, self).__gen_code__(gen)
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

    def __eq__(self, o):
        if not Node.__eq__(self, o):
            return False

        for a in ("name", "size", "offset", "may_overlap", "priority",
            "alias_offset"
        ):
            if getattr(self, a) != getattr(o, a):
                return False

        if idon(self.parent) != idon(o.parent):
            return False
        if idon(self.alias_to) != idon(o.alias_to):
            return False

        schildren = set(c.id for c in self.children)
        ochildren = set(c.id for c in o.children)

        if schildren ^ ochildren:
            return False
        return True


class MemorySASNode(MemoryNode):
    def __init__(self, name, size = None, **kw):
        MemoryNode.__init__(self, name, size, **kw)

class MemoryLeafNode(MemoryNode):
    def add_child(self, *args, **kw):
        raise MemoryNodeCannotHasChildren()

class MemoryAliasNode(MemoryLeafNode):
    def __init__(self, name, size, alias_to, offset = CINT(0), **kw):
        MemoryLeafNode.__init__(self, name, size, **kw)

        self.alias_to = alias_to
        self.alias_offset = CINT(offset)

    def __get_init_arg_val__(self, arg_name):
        if arg_name == "offset":
            arg_name = "alias_offset"
        return getattr(self, arg_name)

class MemoryRAMNode(MemoryLeafNode):
    pass

class MemoryROMNode(MemoryLeafNode):
    pass
