from machine_description import \
    IRQLine, \
    IRQHub, \
    QOMPropertyValue

from project_editing import \
    QemuObjectCreationHelper, \
    DescriptionOperation

import copy

class MachineOperation(DescriptionOperation):
    def __init__(self, machine_description, *args, **kw):
        DescriptionOperation.__init__(self, machine_description, *args, **kw)

    def gen_node_id_entry(self, node_id):
        return copy.deepcopy(node_id)

    @property
    def mach(self):
        return self.desc

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

class MachineNodeAdding(MachineNodeOperation, QemuObjectCreationHelper):
    # node_class_name - string name adding machine node. The class with such
    #     name should be in machine_description module. Class constructor
    #     argument values will be excluded from key word arguments of this
    #     __init__ method.
    def __init__(self, node_class_name, *args, **kw):
        QemuObjectCreationHelper.__init__(self, node_class_name, kw)
        MachineNodeOperation.__init__(self, *args, **kw)

    def __write_set__(self):
        return MachineNodeOperation.__write_set__(self) + [
            self.gen_entry()
        ]

    def __do__(self):
        self.mach.add_node(self.new(), with_id = self.node_id)

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

class MOp_DelDevice(MOp_AddDevice):
    def __init__(self, *args, **kw):
        MOp_AddDevice.__init__(self, "", *args, **kw)

    def __backup__(self):
        dev = self.mach.id2node[self.node_id]

        self.nc = type(dev).__name__
        self.qom_type = str(dev.qom_type)

        if self.nc == "PCIExpressDeviceNode":
            self.slot = copy.deepcopy(dev.slot)
            self.function = copy.deepcopy(dev.function)
            self.multifunction = copy.deepcopy(dev.multifunction)

    __do__ = MOp_AddDevice.__undo__
    __undo__ = MachineNodeAdding.__do__

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

class MOp_DelBus(MOp_AddBus):
    def __init__(self, *args, **kw):
        # SystemBusNode is used to minimize initial sizes of argument & key
        # word argument lists. The actual values will be written by __backup__.
        MOp_AddBus.__init__(self, "SystemBusNode", *args, **kw)

    def __backup__(self):
        bus = self.mach.id2node[self.node_id]

        self.nc = type(bus).__name__
        self.c_type = copy.deepcopy(bus.c_type)
        self.cast = copy.deepcopy(bus.cast)
        self.child_name = copy.deepcopy(bus.child_name)
        self.force_index = copy.deepcopy(bus.force_index)

    __do__ = MOp_AddBus.__undo__
    __undo__ = MOp_AddBus.__do__

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

class MOp_DelIRQLine(MachineNodeOperation):
    def __init__(self, *args, **kw):
        MachineNodeOperation.__init__(self, *args, **kw)

    def __backup__(self):
        irq = self.mach.id2node[self.node_id]

        self.src = copy.deepcopy((irq.src[0].id, irq.src[1], irq.src[2]))
        self.dst = copy.deepcopy((irq.dst[0].id, irq.dst[1], irq.dst[2]))

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
            *copy.deepcopy((self.src[1], self.dst[1], self.src[2], self.dst[2]))
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

        self.src = copy.deepcopy((source_device_id, source_index, source_name))
        self.dst = copy.deepcopy(
            (destination_device_id, destination_index, destination_name)
        )

    def __backup__(self):
        pass

    __do__ = MOp_DelIRQLine.__undo__
    __undo__ = MOp_DelIRQLine.__do__

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

class MOp_DelIRQHub(MOp_AddIRQHub):
    def __init__(self, *args, **kw):
        MOp_AddIRQHub.__init__(self, *args, **kw)

    __do__ = MOp_AddIRQHub.__undo__
    __undo__ = MOp_AddIRQHub.__do__

class MachineDeviceSetAttributeOperation(MachineNodeOperation):
    def __init__(self, attribute_name, new_value, *args, **kw):
        MachineNodeOperation.__init__(self, *args, **kw)

        self.attr = attribute_name
        self.new_val = copy.deepcopy(new_value)

    def __backup__(self):
        dev = self.mach.id2node[self.node_id]
        val = getattr(dev, self.attr)
        self.old_val = copy.deepcopy(val)

    def __do__(self):
        dev = self.mach.id2node[self.node_id]
        setattr(dev, self.attr, copy.deepcopy(self.new_val))

    def __undo__(self):
        dev = self.mach.id2node[self.node_id]
        setattr(dev, self.attr, copy.deepcopy(self.old_val))

    def __read_set__(self):
        return MachineNodeOperation.__read_set__(self) + [
            self.gen_entry()
        ]

    def __write_set__(self):
        return MachineNodeOperation.__write_set__(self) + [
            (self.gen_entry(), "attr", copy.deepcopy(self.attr))
        ]

class MachineNodeSetLinkAttributeOperation(MachineDeviceSetAttributeOperation):
    def __init__(self, attribute_name, new_value, *args, **kw):
        MachineDeviceSetAttributeOperation.__init__(self,
            attribute_name,
            new_value.id,
            *args, **kw
        )

    def __backup__(self):
        node = self.mach.id2node[self.node_id]
        val = getattr(node, self.attr)
        self.old_val = copy.deepcopy(val.id)

    def __do__(self):
        node = self.mach.id2node[self.node_id]
        new_val = self.mach.id2node[self.new_val]
        setattr(node, self.attr, new_val)

    def __undo__(self):
        node = self.mach.id2node[self.node_id]
        old_val = self.mach.id2node[self.old_val]
        setattr(node, self.attr, old_val)

class MOp_PCIDevSetSlot(MachineDeviceSetAttributeOperation):
    def __init__(self, slot, *args, **kw):
        MachineDeviceSetAttributeOperation.__init__(self,
            "slot", slot,
            *args, **kw
        )

class MOp_PCIDevSetFunction(MachineDeviceSetAttributeOperation):
    def __init__(self, function, *args, **kw):
        MachineDeviceSetAttributeOperation.__init__(self,
            "function", function,
            *args, **kw
        )

class MOp_PCIDevSetMultifunction(MachineDeviceSetAttributeOperation):
    def __init__(self, multifunction, *args, **kw):
        MachineDeviceSetAttributeOperation.__init__(self,
            "multifunction", multifunction,
            *args, **kw
        )

class MachineIOMappingOperation(MachineNodeOperation):
    def __init__(self, mio, idx, *args, **kw):
        MachineNodeOperation.__init__(self, *args, **kw)

        self.mio = copy.deepcopy(mio)
        self.idx = copy.deepcopy(idx)

    def __write_set__(self):
        return MachineNodeOperation.__write_set__(self) + [
            (self.gen_entry(), copy.deepcopy(self.mio), 
             copy.deepcopy(self.idx))
        ]

    def __read_set__(self):
        return MachineNodeOperation.__read_set__(self) + [
            self.gen_entry()
        ]

class MOp_DelIOMapping(MachineIOMappingOperation):
    def __backup__(self):
        dev = self.mach.id2node[self.node_id]

        self.old_mapping = copy.deepcopy(
            getattr(dev, self.mio + "_mappings")[self.idx]
        )

    def __do__(self):
        dev = self.mach.id2node[self.node_id]
        mappings = getattr(dev, self.mio + "_mappings")
        del mappings[self.idx]

    def __undo__(self):
        dev = self.mach.id2node[self.node_id]
        mappings = getattr(dev, self.mio + "_mappings")
        mappings[self.idx] = copy.deepcopy(self.old_mapping)

class MOp_AddIOMapping(MachineIOMappingOperation):
    def __init__(self, mapping, *args, **kw):
        MachineIOMappingOperation.__init__(self, *args, **kw)

        self.mapping = copy.deepcopy(mapping)

    def __backup__(self):
        pass

    def __do__(self):
        dev = self.mach.id2node[self.node_id]
        mappings = getattr(dev, self.mio + "_mappings")
        mappings[self.idx] = copy.deepcopy(self.mapping)

    def __undo__(self):
        dev = self.mach.id2node[self.node_id]
        mappings = getattr(dev, self.mio + "_mappings")
        del mappings[self.idx]

class MOp_SetIOMapping(MachineIOMappingOperation):
    def __init__(self, new_mapping, *args, **kw):
        MachineIOMappingOperation.__init__(self, *args, **kw)

        self.new_mapping = copy.deepcopy(new_mapping)

    def __backup__(self):
        dev = self.mach.id2node[self.node_id]

        self.old_mapping = copy.deepcopy(
            getattr(dev, self.mio + "_mappings")[self.idx]
        )

    def __do__(self):
        dev = self.mach.id2node[self.node_id]
        mappings = getattr(dev, self.mio + "_mappings")
        mappings[self.idx] = copy.deepcopy(self.new_mapping)

    def __undo__(self):
        dev = self.mach.id2node[self.node_id]
        mappings = getattr(dev, self.mio + "_mappings")
        mappings[self.idx] = copy.deepcopy(self.old_mapping)

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

class MachineDevicePropertyOperation(MachineNodeOperation):
    def __init__(self, prop, *args, **kw):
        MachineNodeOperation.__init__(self, *args, **kw)
        self.prop_name = copy.deepcopy(prop.prop_name)

    def gen_prop_entry(self):
        return (self.gen_entry(), "prop", copy.deepcopy(self.prop_name))

    def lookup_prop(self):
        dev = self.mach.id2node[self.node_id]
        prop = dev.properties[self.prop_name]
        return prop

    def __read_set__(self):
        return MachineNodeOperation.__read_set__(self) + \
            [ self.gen_entry() ]

class MOp_DelDevProp(MachineDevicePropertyOperation):
    def __init__(self, *args, **kwargs):
        MachineDevicePropertyOperation.__init__(self, *args, **kwargs)

    def __backup__(self):
        prop = self.lookup_prop()

        self.prop_type = prop.prop_type
        self.prop_val = copy.deepcopy(prop.prop_val)

    def __do__(self):
        dev = self.mach.id2node[self.node_id]
        del dev.properties[self.prop_name]

    def __undo__(self):
        prop = QOMPropertyValue(self.prop_type, self.prop_name, self.prop_val)

        dev = self.mach.id2node[self.node_id]

        dev.properties.append(prop)

    def __write_set__(self):
        return MachineDevicePropertyOperation.__write_set__(self) + \
            [ self.gen_prop_entry() ]

class MOp_AddDevProp(MachineNodeOperation):
    def __init__(self, prop, *args, **kw):
        MachineNodeOperation.__init__(self, *args, **kw)

        self.prop_name = copy.deepcopy(prop.prop_name)
        self.prop_type = prop.prop_type
        self.prop_val = copy.deepcopy(prop.prop_val)

    def __backup__(self):
        pass

    def __do__(self):
        prop = QOMPropertyValue(self.prop_type, self.prop_name, self.prop_val)

        dev = self.mach.id2node[self.node_id]

        dev.properties.append(prop)

    def __undo__(self):
        dev = self.mach.id2node[self.node_id]
        del dev.properties[self.prop_name]

    def __write_set__(self):
        return MachineDevicePropertyOperation.__write_set__(self) + \
            [ self.gen_prop_entry() ]

class MOp_SetDevProp(MachineDevicePropertyOperation):
    def __init__(self, new_prop_type, new_prop_val, *args, **kw):
        MachineDevicePropertyOperation.__init__(self, *args, **kw)

        self.new_prop_type = new_prop_type
        self.new_prop_val = copy.deepcopy(new_prop_val)

    def __backup__(self):
        prop = self.lookup_prop()

        self.orig_prop_type = prop.prop_type
        self.orig_prop_val = copy.deepcopy(prop.prop_val)

    def __do__(self):
        prop = self.lookup_prop()

        prop.prop_type = self.new_prop_type
        prop.prop_val = copy.deepcopy(self.new_prop_val)

    def __undo__(self):
        prop = self.lookup_prop()

        prop.prop_type = self.orig_prop_type
        prop.prop_val = copy.deepcopy(self.orig_prop_val)

    def __write_set__(self):
        return MachineDevicePropertyOperation.__write_set__(self) + \
            [ self.gen_prop_entry() ]
