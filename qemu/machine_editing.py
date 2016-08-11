from common.inverse_operation import \
    HistoryTracker, \
    InverseOperation

from machine_description import \
    IRQHub, \
    QOMPropertyValue

import copy

class MachineOperation(InverseOperation):
    def __init__(self, machine_description, *args, **kw):
        InverseOperation.__init__(self, *args, **kw)
        self.mach = machine_description

    def gen_node_id_entry(self, node_id):
        return copy.deepcopy(node_id)

    """
    The InverseOperation defines no read or write sets. Instead it raises an
    exception. As this is a base class of all machine editing operations it
    should define the sets. The content of the sets is to be defined by
    subclasses.
    """

    def __write_set__(self):
        return []

    def __read_set__(self):
        return []

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
        return self.gen_entry() in self.__write_set__()

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

        if hub.srcs or hub.dsts:
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

class MachineHistoryTracker(HistoryTracker):
    def __init__(self, machine_description, *args, **kw):
        HistoryTracker.__init__(self, *args, **kw)
        self.mach = machine_description

    def stage(self, op_class,  *op_args, **op_kw):
        return HistoryTracker.stage(self,
            op_class,
            *(op_args + (self.mach,)), **op_kw
        )
