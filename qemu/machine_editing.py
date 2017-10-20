from .qom import QOMPropertyValue
from .machine_nodes import (
    DeviceNode,
    BusNode,
    Node,
    MemoryNode,
    MemoryAliasNode,
    MemoryROMNode,
    MemoryRAMNode,
    QOMPropertyTypeLink,
    IRQLine,
    IRQHub
)
from .project_editing import (
    QemuObjectCreationHelper,
    DescriptionOperation
)
from copy import deepcopy
from common import mlget as _
from six import integer_types

class MachineOperation(DescriptionOperation):
    def __init__(self, machine_description, *args, **kw):
        DescriptionOperation.__init__(self, machine_description, *args, **kw)

    def gen_node_id_entry(self, node_id):
        return deepcopy(node_id)

    """ Converts invariant link property value to python object reference used
across machine description object. Non-link property values is just deeply
copied. Invariant link value is an integer now. """
    def prop_val_2_ref(self, prop_type, prop_val):
        if prop_type == QOMPropertyTypeLink:
            if prop_val == -1:
                return None
            else:
                return self.mach.id2node[prop_val]
        else:
            return deepcopy(prop_val)

    """ Converts link property value presented by python object reference to
invariant values (independent from the machine description instance). Non-link
property values is just deeply copied. """
    def prop_val_2_inv(self, prop_type, prop_val):
        if prop_type == QOMPropertyTypeLink:
            if prop_val is None:
                return -1
            else:
                return deepcopy(prop_val.id)
        else:
            return deepcopy(prop_val)

    @property
    def mach(self):
        return self.find_desc()

class MachineNodeOperation(MachineOperation):
    def __init__(self, node_id, *args, **kw):
        MachineOperation.__init__(self, *args, **kw)

        self.node_id = node_id

    def gen_entry(self):
        return self.gen_node_id_entry(self.node_id)

    """
    Checks if the operation writes the node itself (not node's element)
    Frequent examples are node adding and deleting operations.
    """
    def writes_node(self):
        return self.writes(self.gen_entry())

    def gen_id_str(self, val):
        if val < 0:
            return "NULL"

        mach = self.find_desc()
        node = mach.id2node[val]

        if isinstance(node, DeviceNode):
            node_kind_str = _("device '%s'") % node.qom_type
        elif isinstance(node, BusNode):
            node_kind_str = _("bus '%s'") % node.child_name
        elif isinstance(node, MemoryNode):
            node_kind_str = _("memory region '%s'") % node.name
        elif isinstance(node, IRQLine):
            node_kind_str = _("IRQ line")
        elif isinstance(node, IRQHub):
            node_kind_str = _("IRQ hub")
        else:
            node_kind_str = _("node")

        return _("%s (%d)") % (node_kind_str, val)

class MOp_AddMemChild(MachineNodeOperation):
    def __init__(self, child_id, *args, **kw):
        MachineNodeOperation.__init__(self, *args, **kw)
        self.child_id = deepcopy(child_id)

    def __backup__(self):
        pass

    def __do__(self):
        m = self.find_desc()
        child, parent = m.id2node[self.child_id], m.id2node[self.node_id]

        parent.add_child(child)

    def __undo__(self):
        m = self.find_desc()
        child, parent = m.id2node[self.child_id], m.id2node[self.node_id]

        parent.remove_child(child)

    def __read_set__(self):
        return MachineNodeOperation.__read_set__(self) + [
            self.gen_node_id_entry(self.child_id), self.gen_entry()
        ]

    def __write_set__(self):
        """ Because order of children is not important, we are only have to
organize operations about same child. """

        return MachineNodeOperation.__write_set__(self) + [
            (self.gen_entry(), "__child__", \
                self.gen_node_id_entry(self.child_id))
        ]

    def __description__(self):
        mach = self.find_desc()
        return _("Include memory region %s (%d) to %s (%d).") % (
            mach.id2node[self.child_id].name, self.child_id,
            mach.id2node[self.node_id].name, self.node_id
        )

class MOp_RemoveMemChild(MOp_AddMemChild):

    __do__ = MOp_AddMemChild.__undo__
    __undo__ = MOp_AddMemChild.__do__

    def __description__(self):
        mach = self.find_desc()
        return _("Exclude memory region %s (%d) from %s (%d).") % (
            mach.id2node[self.child_id].name, self.child_id,
            mach.id2node[self.node_id].name, self.node_id
        )

def node_import_helper(node, operation):
    return node.id

def node_export_helper(node_id, operation):
    return operation.find_desc().id2node[node_id]

class MachineNodeAdding(MachineNodeOperation, QemuObjectCreationHelper):
    value_import_helpers = dict(QemuObjectCreationHelper.value_import_helpers)
    value_export_helpers = dict(QemuObjectCreationHelper.value_export_helpers)

    value_import_helpers[Node] = node_import_helper
    value_export_helpers[Node] = node_export_helper

    # node_class_name - string name adding machine node. The class with such
    #     name should be in machine_description module. Class constructor
    #     argument values will be excluded from key word arguments of this
    #     __init__ method.
    def __init__(self, node_class_name, *args, **kw):
        QemuObjectCreationHelper.__init__(self, arg_name_prefix = "node__")
        self.nc = node_class_name
        self.pop_args_from_dict(kw)
        MachineNodeOperation.__init__(self, *args, **kw)

    def __write_set__(self):
        return MachineNodeOperation.__write_set__(self) + [
            self.gen_entry()
        ]

    def __do__(self):
        self.mach.add_node(self.new(), with_id = self.node_id)

class MachineNodeDeletion(MachineNodeAdding):
    def __init__(self, *args, **kw):
        MachineNodeAdding.__init__(self, "", *args, **kw)

    def __backup__(self):
        n = self.find_desc().id2node[self.node_id]
        self.set_with_origin(n)

    __undo__ = MachineNodeAdding.__do__

class MOp_AddMemoryNode(MachineNodeAdding):

    def __backup__(self):
        pass

    def __undo__(self):
        mach = self.find_desc()
        mem = mach.id2node[self.node_id]

        if mem.children:
            raise Exception("Memory node %d has children" % self.node_id)

        if mem.parent:
            raise Exception("Memory node %d has parent %d" % mem.parent.id)

        for n in mach.id2node.values():
            if isinstance(n, MemoryAliasNode):
                if n.alias_to is mem:
                    raise Exception(
"Memory node to be deleted %d is aliased by node %d" % (self.node_id, n.id)
                    )

        mach.mems.remove(mem)
        del mach.id2node[self.node_id]
        mem.id = -1

    def get_kind_str(self):
        if MemoryNode.__name__ in self.nc:
            return _("container")
        elif MemoryAliasNode.__name__ in self.nc:
            aliased = self.get_arg("alias_to")
            # TODO: offset is keyword argument, cannot be obtained by get_arg
            aliased_offset = self.get_arg("offset")

            if isinstance(aliased_offset, integer_types):
                aliased_offset = "0x%X" % aliased_offset
            else:
                aliased_offset = str(aliased_offset)

            return _("alias of %s (%d) with offset %s") % (
                aliased.name, aliased.id,
                aliased_offset
            )
        elif MemoryRAMNode.__name__ in self.nc:
            return _("RAM")
        elif MemoryROMNode.__name__ in self.nc:
            return _("ROM")
        else:
            return "!"

    def __description__(self):
        name = self.get_arg("name")
        return _("Create memory region %s (%d) of kind %s.") % (
            name, self.node_id,
            self.get_kind_str()
        )

class MOp_DelMemoryNode(MachineNodeDeletion, MOp_AddMemoryNode):
    def __init__(self, *args, **kw):
        MachineNodeDeletion.__init__(self, *args, **kw)

    __do__ =  MOp_AddMemoryNode.__undo__

    def __description__(self):
        name = self.get_arg("name")
        return _("Delete memory region %s (%d) of kind %s.") % (
            name, self.node_id,
            self.get_kind_str()
        )

class MOp_AddDevice(MachineNodeAdding):
    def __init__(self, device_class_name, *args, **kw):
        MachineNodeAdding.__init__(self, device_class_name, *args, **kw)

    def __backup__(self):
        pass

    def __undo__(self):
        dev = self.mach.id2node[self.node_id]

        if not dev.parent_bus is None:
            raise Exception("Device %i should not be connected to a bus" %
                self.node_id)

        if dev.buses:
            raise Exception("Device %i should not have child buses" %
                self.node_id)

        if dev.irqs:
            raise Exception("Device %i should not be linked by IRQs" %
                self.node_id)

        if dev.properties:
            raise Exception("Device %i should not have properties" %
                self.node_id)

        # TODO: Checking for MMIOs, PMIOs & so on might be useful too

        self.mach.devices.remove(dev)
        del self.mach.id2node[self.node_id]
        dev.id = -1

    def get_kind_str(self):
        if "SystemBusDeviceNode" in self.nc:
            return _("system bus device")
        elif "PCIExpressDeviceNode" in self.nc:
            return _("PCI(E) function")
        elif "DeviceNode" in self.nc:
            return _("generic device")

    def __description__(self):
        return _("Create %s (%d) of type '%s'.") % (
            self.get_kind_str(),
            self.node_id,
            self.get_arg("qom_type")
        )

class MOp_DelDevice(MOp_AddDevice):
    def __init__(self, *args, **kw):
        MOp_AddDevice.__init__(self, "", *args, **kw)

    def __backup__(self):
        dev = self.mach.id2node[self.node_id]
        self.set_with_origin(dev)

    __do__ = MOp_AddDevice.__undo__
    __undo__ = MachineNodeAdding.__do__

    def __description__(self):
        return _("Delete %s (%d) of type '%s'.") % (
            self.get_kind_str(),
            self.node_id,
            self.get_arg("qom_type")
        )

class MOp_AddBus(MachineNodeAdding):
    def __init__(self, bus_class_name, *args, **kw):
        MachineNodeAdding.__init__(self, bus_class_name, *args, **kw)

    def __backup__(self):
        pass

    def __undo__(self):
        bus = self.mach.id2node[self.node_id]

        if bus.parent_device:
            raise Exception("Bus %i should not have parent" % self.node_id)

        if bus.devices:
            raise Exception("Bus %i should not have children" % self.node_id)

        self.mach.buses.remove(bus)
        del self.mach.id2node[self.node_id]
        bus.id = -1

    def get_kind_str(self):
        if "SystemBusNode" in self.nc:
            return _("system bus")
        elif "PCIExpressBusNode" in self.nc:
            return _("PCI(E) bus")
        elif "ISABusNode" in self.nc:
            return _("ISA bus")
        elif "IDEBusNod" in self.nc:
            return _("IDE bus")
        elif "I2CBusNode" in self.nc:
            return _("I2C bus")
        elif "BusNode" in self.nc:
            return "generic bus"

    def __description__(self):
        return _("Create %s (%d).") % (
            self.get_kind_str(),
            self.node_id
        )

class MOp_DelBus(MOp_AddBus):
    def __init__(self, *args, **kw):
        # SystemBusNode is used to minimize initial sizes of argument & key
        # word argument lists. The actual values will be written by __backup__.
        MOp_AddBus.__init__(self, "SystemBusNode", *args, **kw)

    def __backup__(self):
        bus = self.mach.id2node[self.node_id]
        self.set_with_origin(bus)

    __do__ = MOp_AddBus.__undo__
    __undo__ = MOp_AddBus.__do__

    def __description__(self):
        return _("Delete %s (%d).") % (
            self.get_kind_str(),
            self.node_id
        )

class MOp_SetChildBus(MachineOperation):
    def __init__(self, dev_id, child_idx, bus_id, *args, **kw):
        MachineOperation.__init__(self, *args, **kw)

        self.dev_id, self.idx, self.bus_id = dev_id, child_idx, bus_id

    def __backup__(self):
        dev = self.mach.id2node[self.dev_id]
        try:
            self.prev_bus_id = dev.buses[self.idx].id
        except IndexError:
            self.prev_bus_id = -1

    @staticmethod
    def swap_child_bus(mach, dev_id, idx, new_bus_id):
        dev = mach.id2node[dev_id]

        if new_bus_id == -1:
            try:
                cur_bus = dev.buses.pop(idx)
            except IndexError:
                raise Exception("Device %i has no bus at index %i" % \
                    (dev_id, idx))
            else:
                cur_bus.parent_device = None
        else:
            new_bus = mach.id2node[new_bus_id]
            if new_bus.parent_device:
                raise Exception("Bus %i already has parent" % new_bus.id)

            new_bus.parent_device = dev

            if idx == len(dev.buses):
                dev.buses.append(new_bus)
            else:
                dev.buses[idx].parent_device = None
                dev.buses[idx] = new_bus

    def __do__(self):
        MOp_SetChildBus.swap_child_bus(self.mach, self.dev_id, self.idx,
            self.bus_id)

    def __undo__(self):
        MOp_SetChildBus.swap_child_bus(self.mach, self.dev_id, self.idx,
            self.prev_bus_id)

    def __read_set__(self):
        return MachineOperation.__read_set__(self) + [
            self.gen_node_id_entry(i) for i in [
                self.dev_id, self.bus_id, self.prev_bus_id
            ] if not i == -1
        ]

    def __write_set__(self):
        ret = MachineOperation.__write_set__(self) + [
            (self.gen_node_id_entry(self.dev_id), "buses")
        ]
        if not self.bus_id == -1:
            ret.append((self.gen_node_id_entry(self.bus_id), "parent_device"))
        if not self.prev_bus_id == -1:
            ret.append(
                (self.gen_node_id_entry(self.prev_bus_id),"parent_device")
            )
        return ret

    def __description__(self):
        mach = self.find_desc()
        if self.prev_bus_id == -1:
            return _("Make device %s (%d) a controller of bus %s (%d) with \
index %d.") % (
                mach.id2node[self.dev_id].qom_type, self.dev_id,
                mach.id2node[self.bus_id].child_name, self.bus_id,
                self.idx
            )
        elif self.bus_id == -1:
            return _("Disconnect bus %s (%d) from index %d of controller %s \
(%d).") % (
                mach.id2node[self.prev_bus_id].child_name, self.prev_bus_id,
                self.idx,
                mach.id2node[self.dev_id].qom_type, self.dev_id
            )
        else:
            return _("Replace bus %s (%d) with %s (%d) in controller %s (%d)\
at index %d.") % (
                mach.id2node[self.prev_bus_id].child_name, self.prev_bus_id,
                mach.id2node[self.bus_id].child_name, self.bus_id,
                mach.id2node[self.dev_id].qom_type, self.dev_id,
                self.idx
            )

class MOp_DelIRQLine(MachineNodeOperation):
    def __init__(self, *args, **kw):
        MachineNodeOperation.__init__(self, *args, **kw)

    def __backup__(self):
        irq = self.mach.id2node[self.node_id]

        self.src = deepcopy((irq.src[0].id, irq.src[1], irq.src[2]))
        self.dst = deepcopy((irq.dst[0].id, irq.dst[1], irq.dst[2]))

    def __do__(self):
        irq = self.mach.id2node[self.node_id]

        src_dev = self.mach.id2node[self.src[0]]
        src_dev.irqs.remove(irq)

        dst_dev = self.mach.id2node[self.dst[0]]
        dst_dev.irqs.remove(irq)

        self.mach.irqs.remove(irq)
        del self.mach.id2node[self.node_id]
        irq.id = -1

    def __undo__(self):
        irq = IRQLine(
            self.mach.id2node[self.src[0]], self.mach.id2node[self.dst[0]],
            *deepcopy((self.src[1], self.dst[1], self.src[2], self.dst[2]))
        )

        self.mach.add_node(irq, with_id = self.node_id)

    def __read_set__(self):
        return MachineNodeOperation.__read_set__(self) + [
            self.gen_node_id_entry(e) for e in [self.src[0], self.dst[0]]
        ]

    def __write_set__(self):
        return MachineNodeOperation.__write_set__(self) + [
            self.gen_entry()
        ]

    def gen_end_str(self, eid, idx, name):
        mach = self.find_desc()

        end_node = mach.id2node[eid]
        if isinstance(end_node, DeviceNode):
            if name:
                return _("%s %s out of device %s (%d)") % (
                    name, str(idx),
                    end_node.qom_type, eid
                )
            else:
                return _("unnamed %s out of device %s (%d)") % (
                    str(idx),
                    end_node.qom_type, eid
                )
        elif isinstance(end_node, IRQHub):
            return _("IRQ hub (%d)") % eid
        else:
            return "!"

    def __description__(self):
        return _("Delete IRQ line (%d) from %s to %s.") % (
            self.node_id,
            self.gen_end_str(*self.src),
            self.gen_end_str(*self.dst)
        )

class MOp_AddIRQLine(MOp_DelIRQLine):
    def __init__(self,
        source_device_id,
        destination_device_id,
        source_index,
        destination_index,
        source_name,
        destination_name,
        *args, **kw
    ):
        MOp_DelIRQLine.__init__(self, *args, **kw)

        self.src = deepcopy((source_device_id, source_index, source_name))
        self.dst = deepcopy(
            (destination_device_id, destination_index, destination_name)
        )

    def __backup__(self):
        pass

    __do__ = MOp_DelIRQLine.__undo__
    __undo__ = MOp_DelIRQLine.__do__

    def __description__(self):
        return _("Create IRQ line (%d) from %s to %s.") % (
            self.node_id,
            self.gen_end_str(*self.src),
            self.gen_end_str(*self.dst)
        )

class MOp_AddIRQHub(MachineNodeOperation):
    def __init__(self, *args, **kw):
        MachineNodeOperation.__init__(self, *args, **kw)

    def __backup__(self):
        pass

    def __do__(self):
        hub = IRQHub([], [])
        self.mach.add_node(hub, with_id = self.node_id)

    def __undo__(self):
        hub = self.mach.id2node[self.node_id]

        if hub.irqs:
            raise Exception("The hub has connected IRQs")

        self.mach.irq_hubs.remove(hub)
        del self.mach.id2node[self.node_id]
        hub.id = -1

    def __write_set__(self):
        return MachineNodeOperation.__write_set__(self) + [ self.gen_entry() ]

    def __description__(self):
        return _("Create IRQ hub (%d).") % self.node_id

class MOp_DelIRQHub(MOp_AddIRQHub):
    def __init__(self, *args, **kw):
        MOp_AddIRQHub.__init__(self, *args, **kw)

    __do__ = MOp_AddIRQHub.__undo__
    __undo__ = MOp_AddIRQHub.__do__

    def __description__(self):
        return _("Delete IRQ hub (%d).") % self.node_id

class MachineNodeSetAttributeOperation(MachineNodeOperation):
    def __init__(self, attribute_name, new_value, *args, **kw):
        MachineNodeOperation.__init__(self, *args, **kw)

        self.attr = attribute_name
        self.new_val = deepcopy(new_value)

    def __backup__(self):
        node = self.mach.id2node[self.node_id]
        val = getattr(node, self.attr)
        self.old_val = deepcopy(val)

    def __do__(self):
        node = self.mach.id2node[self.node_id]
        setattr(node, self.attr, deepcopy(self.new_val))

    def __undo__(self):
        dev = self.mach.id2node[self.node_id]
        setattr(dev, self.attr, deepcopy(self.old_val))

    def __read_set__(self):
        return MachineNodeOperation.__read_set__(self) + [
            self.gen_entry()
        ]

    def __write_set__(self):
        return MachineNodeOperation.__write_set__(self) + [
            (self.gen_entry(), "attr", deepcopy(self.attr))
        ]

    def gen_val_str(self, val):
        if isinstance(val, integer_types):
            if val < 0:
                return "%d" % val
            else:
                return "0x%X" % val
        else:
            return str(val)

    def __description__(self):
        return _("Replace value '%s' of attribute '%s' of %s with value '%s'."
        ) % (
            self.gen_val_str(self.old_val),
            self.attr,
            self.gen_id_str(self.node_id),
            self.gen_val_str(self.new_val)
        )

class MOp_SetNodeVarNameBase(MachineNodeSetAttributeOperation):
    def __init__(self, new_base, *args, **kw):
        super(MOp_SetNodeVarNameBase, self).__init__("var_base", new_base,
            *args, **kw
        )

class MOp_SetMemNodeAttr(MachineNodeSetAttributeOperation):
    pass

class MachineNodeSetLinkAttributeOperation(MachineNodeSetAttributeOperation):
    def __init__(self, attribute_name, new_value, *args, **kw):
        MachineNodeSetAttributeOperation.__init__(self,
            attribute_name,
            new_value.id,
            *args, **kw
        )

    def __backup__(self):
        node = self.mach.id2node[self.node_id]
        val = getattr(node, self.attr)
        self.old_val = deepcopy(val.id)

    def __do__(self):
        node = self.mach.id2node[self.node_id]
        new_val = self.mach.id2node[self.new_val]
        setattr(node, self.attr, new_val)

    def __undo__(self):
        node = self.mach.id2node[self.node_id]
        old_val = self.mach.id2node[self.old_val]
        setattr(node, self.attr, old_val)

    def gen_val_str(self, val):
        return self.gen_id_str(val)

class MOp_PCIDevSetSlot(MachineNodeSetAttributeOperation):
    def __init__(self, slot, *args, **kw):
        MachineNodeSetAttributeOperation.__init__(self,
            "slot", slot,
            *args, **kw
        )

class MOp_PCIDevSetFunction(MachineNodeSetAttributeOperation):
    def __init__(self, function, *args, **kw):
        MachineNodeSetAttributeOperation.__init__(self,
            "function", function,
            *args, **kw
        )

class MOp_PCIDevSetMultifunction(MachineNodeSetAttributeOperation):
    def __init__(self, multifunction, *args, **kw):
        MachineNodeSetAttributeOperation.__init__(self,
            "multifunction", multifunction,
            *args, **kw
        )

class MOp_SetIRQAttr(MachineNodeSetAttributeOperation):
    pass

class MOp_SetIRQEndPoint(MachineNodeSetLinkAttributeOperation):
    def __description__(self):
        mach = self.find_desc()
        dev = mach.id2node[self.node_id]

        return _("Replace %s '%s' of IRQ line %d with value '%s'.\
") % (
            _("source end-point") if "src" in self.attr \
                else _("destination end-point"),
            self.gen_id_str(self.old_val),
            self.node_id,
            self.gen_id_str(self.new_val)
        )

class MOp_SetMemNodeAlias(MachineNodeSetLinkAttributeOperation):
    def __description__(self):
        mach = self.find_desc()
        mem = mach.id2node[self.node_id]

        return _("Redirect memory alias '%s' (%d) from %s to %s.\
") % (
            mem.name,
            self.node_id,
            self.gen_id_str(self.old_val),
            self.gen_id_str(self.new_val)
        )

class MOp_SetBusAttr(MachineNodeSetAttributeOperation):
    pass

class MachineIOMappingOperation(MachineNodeOperation):
    def __init__(self, mio, idx, *args, **kw):
        MachineNodeOperation.__init__(self, *args, **kw)

        self.mio = deepcopy(mio)
        self.idx = deepcopy(idx)

    def __write_set__(self):
        return MachineNodeOperation.__write_set__(self) + [
            (self.gen_entry(), deepcopy(self.mio), 
             deepcopy(self.idx))
        ]

    def __read_set__(self):
        return MachineNodeOperation.__read_set__(self) + [
            self.gen_entry()
        ]

    def gen_val_str(self, val):
        if isinstance(val, integer_types):
            if val < 0:
                return "-0x%X" % -val
            else:
                return "0x%X" % val
        else:
            return str(val)

class MOp_DelIOMapping(MachineIOMappingOperation):
    def __backup__(self):
        dev = self.mach.id2node[self.node_id]

        self.old_mapping = deepcopy(
            getattr(dev, self.mio + "_mappings")[self.idx]
        )

    def __do__(self):
        dev = self.mach.id2node[self.node_id]
        mappings = getattr(dev, self.mio + "_mappings")
        del mappings[self.idx]

    def __undo__(self):
        dev = self.mach.id2node[self.node_id]
        mappings = getattr(dev, self.mio + "_mappings")
        mappings[self.idx] = deepcopy(self.old_mapping)

    def __description__(self):
        return _("Delete %s %s mapping from index %d of %s.") % (
            self.mio.upper(),
            self.gen_val_str(self.old_mapping),
            self.idx,
            self.gen_id_str(self.node_id)
        )

class MOp_AddIOMapping(MachineIOMappingOperation):
    def __init__(self, mapping, *args, **kw):
        MachineIOMappingOperation.__init__(self, *args, **kw)

        self.mapping = deepcopy(mapping)

    def __backup__(self):
        pass

    def __do__(self):
        dev = self.mach.id2node[self.node_id]
        mappings = getattr(dev, self.mio + "_mappings")
        mappings[self.idx] = deepcopy(self.mapping)

    def __undo__(self):
        dev = self.mach.id2node[self.node_id]
        mappings = getattr(dev, self.mio + "_mappings")
        del mappings[self.idx]

    def __description__(self):
        return _("Add %s %s mapping to index %d of %s.") % (
            self.mio.upper(),
            self.gen_val_str(self.mapping),
            self.idx,
            self.gen_id_str(self.node_id)
        )

class MOp_SetIOMapping(MachineIOMappingOperation):
    def __init__(self, new_mapping, *args, **kw):
        MachineIOMappingOperation.__init__(self, *args, **kw)

        self.new_mapping = deepcopy(new_mapping)

    def __backup__(self):
        dev = self.mach.id2node[self.node_id]

        self.old_mapping = deepcopy(
            getattr(dev, self.mio + "_mappings")[self.idx]
        )

    def __do__(self):
        dev = self.mach.id2node[self.node_id]
        mappings = getattr(dev, self.mio + "_mappings")
        mappings[self.idx] = deepcopy(self.new_mapping)

    def __undo__(self):
        dev = self.mach.id2node[self.node_id]
        mappings = getattr(dev, self.mio + "_mappings")
        mappings[self.idx] = deepcopy(self.old_mapping)

    def __description__(self):
        return _("Replace %s %s mapping at index %d of %s with %s.") % (
            self.mio.upper(),
            self.gen_val_str(self.old_mapping),
            self.idx,
            self.gen_id_str(self.node_id),
            self.gen_val_str(self.new_mapping)
        )

class MOp_SetDevParentBus(MachineNodeOperation):
    def __init__(self, new_bus, *args, **kw):
        MachineNodeOperation.__init__(self, *args, **kw)

        self.new_bus_id = new_bus.id if new_bus else -1

    def __backup__(self):
        dev = self.mach.id2node[self.node_id]
        self.old_bus_id = dev.parent_bus.id if dev.parent_bus else -1

    def __do__(self):
        dev = self.mach.id2node[self.node_id]

        if dev.parent_bus:
            dev.parent_bus.devices.remove(dev)

        if self.new_bus_id < 0:
            dev.parent_bus = None
        else:
            parent_bus = self.mach.id2node[self.new_bus_id]
            dev.parent_bus = parent_bus
            parent_bus.devices.append(dev)

    def __undo__(self):
        dev = self.mach.id2node[self.node_id]

        if dev.parent_bus:
            dev.parent_bus.devices.remove(dev)

        if self.old_bus_id < 0:
            dev.parent_bus = None
        else:
            parent_bus = self.mach.id2node[self.old_bus_id]
            dev.parent_bus = parent_bus
            parent_bus.devices.append(dev)

    def __write_set__(self):
        return MachineNodeOperation.__write_set__(self) + \
            [ (self.gen_entry(), "parent_bus") ]

    def __read_set__(self):
        ret = MachineNodeOperation.__write_set__(self) + \
            [ self.gen_entry() ]
        if self.new_bus_id >= 0:
            ret = ret + [ self.gen_node_id_entry(self.new_bus_id) ]
        if self.old_bus_id >= 0:
            ret = ret + [ self.gen_node_id_entry(self.old_bus_id) ]
        return ret

    def __description__(self):
        if self.new_bus_id < 0:
            return _("Detach %s from %s.") % (
                self.gen_id_str(self.node_id),
                self.gen_id_str(self.old_bus_id)
            )
        elif self.old_bus_id < 0:
            return _("Attach %s to %s.") % (
                self.gen_id_str(self.node_id),
                self.gen_id_str(self.new_bus_id)
            )
        else:
            return _("Move %s from %s to %s.") % (
                self.gen_id_str(self.node_id),
                self.gen_id_str(self.old_bus_id),
                self.gen_id_str(self.new_bus_id)
            )

class MOp_SetDevQOMType(MachineNodeOperation):
    def __init__(self, new_type_name, *args, **kw):
        MachineNodeOperation.__init__(self, *args, **kw)

        self.new_type_name = new_type_name

    def __write_set__(self):
        return MachineNodeOperation.__write_set__(self) + \
            [ (self.gen_entry(), "qom_type") ]

    def __backup__(self):
        dev = self.mach.id2node[self.node_id]
        self.old_type_name = dev.qom_type

    def __do__(self):
        dev = self.mach.id2node[self.node_id]
        dev.qom_type = self.new_type_name

    def __undo__(self):
        dev = self.mach.id2node[self.node_id]
        dev.qom_type = self.old_type_name

    def __description__(self):
        return _("Change QOM type of device (%u) from '%s' to '%s'.") % (
            self.node_id, self.old_type_name, self.new_type_name
        )

class MachineDevicePropertyOperation(MachineNodeOperation):
    def __init__(self, prop, *args, **kw):
        MachineNodeOperation.__init__(self, *args, **kw)
        self.prop_name = deepcopy(prop.prop_name)

    def gen_prop_entry(self):
        return (self.gen_entry(), "prop", deepcopy(self.prop_name))

    def lookup_prop(self):
        dev = self.mach.id2node[self.node_id]
        prop = dev.properties[self.prop_name]
        return prop

    def __read_set__(self):
        return MachineNodeOperation.__read_set__(self) + \
            [ self.gen_entry() ]

    def gen_val_str(self, p_type, p_val):
        if p_type == QOMPropertyTypeLink:
            return self.gen_id_str(p_val)
        elif isinstance(p_val, integer_types):
            if p_val < 0:
                return "-0x%X" % p_val
            else:
                return "0x%X" % p_val
        else:
            return str(p_val)

class MOp_DelDevProp(MachineDevicePropertyOperation):
    def __init__(self, *args, **kwargs):
        MachineDevicePropertyOperation.__init__(self, *args, **kwargs)

    def __backup__(self):
        prop = self.lookup_prop()

        # print "%s %s -> %s" % (prop.prop_name, prop.prop_type.__name__,
        #     str(prop.prop_val))

        self.prop_type = prop.prop_type
        self.prop_val = self.prop_val_2_inv(prop.prop_type, prop.prop_val)

    def __do__(self):
        dev = self.mach.id2node[self.node_id]
        del dev.properties[self.prop_name]

    def __undo__(self):
        prop = QOMPropertyValue(self.prop_type, self.prop_name,
            self.prop_val_2_ref(self.prop_type, self.prop_val))

        dev = self.mach.id2node[self.node_id]

        dev.properties.append(prop)

        # print "%s %s <- %s" % (prop.prop_name, prop.prop_type.__name__,
        #     str(prop.prop_val))

    def __write_set__(self):
        return MachineDevicePropertyOperation.__write_set__(self) + \
            [ self.gen_prop_entry() ]

    def __description__(self):
        return _("Delete property '%s' with value %s from device %s (%d)."
) % (
            self.prop_name,
            self.gen_val_str(self.prop_type, self.prop_val),
            self.find_desc().id2node[self.node_id].qom_type, self.node_id
        )

class MOp_AddDevProp(MachineDevicePropertyOperation):
    def __init__(self, prop, *args, **kw):
        MachineDevicePropertyOperation.__init__(self, prop, *args, **kw)

        self.prop_type = prop.prop_type
        self.prop_val = self.prop_val_2_inv(prop.prop_type, prop.prop_val)

    def __backup__(self):
        pass

    def __do__(self):
        prop = QOMPropertyValue(self.prop_type, self.prop_name,
            self.prop_val_2_ref(self.prop_type, self.prop_val))

        dev = self.mach.id2node[self.node_id]

        dev.properties.append(prop)

    def __undo__(self):
        dev = self.mach.id2node[self.node_id]
        del dev.properties[self.prop_name]

    def __write_set__(self):
        return MachineDevicePropertyOperation.__write_set__(self) + \
            [ self.gen_prop_entry() ]

    def __description__(self):
        return _("Add property '%s' with value %s to device %s (%d)."
) % (
            self.prop_name,
            self.gen_val_str(self.prop_type, self.prop_val),
            self.find_desc().id2node[self.node_id].qom_type, self.node_id
        )

class MOp_SetDevProp(MachineDevicePropertyOperation):
    def __init__(self, new_prop_type, new_prop_val, *args, **kw):
        MachineDevicePropertyOperation.__init__(self, *args, **kw)

        self.new_prop_type = new_prop_type
        self.new_prop_val = self.prop_val_2_inv(new_prop_type, new_prop_val)

    def __backup__(self):
        prop = self.lookup_prop()

        self.orig_prop_type = prop.prop_type
        self.orig_prop_val = self.prop_val_2_inv(prop.prop_type, prop.prop_val)

        # print "%s %s -> %s (orig)" % (prop.prop_name, prop.prop_type.__name__,
        #     str(prop.prop_val))

    def __do__(self):
        prop = self.lookup_prop()

        prop.prop_type = self.new_prop_type
        prop.prop_val = self.prop_val_2_ref(self.new_prop_type,
            self.new_prop_val)

        # print "%s %s <- %s (new)" % (prop.prop_name, prop.prop_type.__name__,
        #     str(prop.prop_val))

    def __undo__(self):
        prop = self.lookup_prop()

        prop.prop_type = self.orig_prop_type

        prop.prop_val = self.prop_val_2_ref(self.orig_prop_type,
            self.orig_prop_val)

        # print "%s %s <- %s (orig)" % (prop.prop_name, prop.prop_type.__name__,
        #     str(prop.prop_val))

    def __write_set__(self):
        return MachineDevicePropertyOperation.__write_set__(self) + \
            [ self.gen_prop_entry() ]

    def __description__(self):
        return _("Replace property '%s' value %s of device %s (%d) with \
value %s.") % (
            self.prop_name,
            self.gen_val_str(self.orig_prop_type, self.orig_prop_val),
            self.find_desc().id2node[self.node_id].qom_type, self.node_id,
            self.gen_val_str(self.new_prop_type, self.new_prop_val),
        )
