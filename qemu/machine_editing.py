from common.inverse_operation import \
    HistoryTracker, \
    InverseOperation

from machine_description import \
    QOMPropertyValue

import copy

class MachineOperation(InverseOperation):
    def __init__(self, machine_description, *args, **kw):
        InverseOperation.__init__(self, *args, **kw)
        self.mach = machine_description

    def gen_node_id_entry(self, node_id):
        return copy.deepcopy(node_id)

class MachineDeviceOperation(MachineOperation):
    def __init__(self, device_id, *args, **kw):
        MachineOperation.__init__(self, *args, **kw)
        self.dev_id = copy.deepcopy(device_id)

    def gen_dev_entry(self):
        return copy.deepcopy(self.device_id)

class MOp_SetDevQOMType(MachineDeviceOperation):
    def __init__(self, new_type_name, *args, **kw):
        MachineDeviceOperation.__init__(self, *args, **kw)

        self.new_type_name = new_type_name

    def __write_set__(self):
        return MachineDeviceOperation.__write_set__(self) + \
            [ (self.gen_dev_entry(), "qom_type") ]

    def __backup__(self):
        dev = self.mach.id2node[self.dev_id]
        self.old_type_name = dev.qom_type

    def __do__(self):
        dev = self.mach.id2node[self.dev_id]
        dev.qom_type = self.new_type_name

    def __undo__(self):
        dev = self.mach.id2node[self.dev_id]
        dev.qom_type = self.old_type_name

class MachineDevicePropertyOperation(MachineDeviceOperation):
    def __init__(self, prop, *args, **kw):
        MachineDeviceOperation.__init__(self, *args, **kw)
        self.prop_name = copy.deepcopy(prop.prop_name)

    def gen_prop_entry(self):
        return (self.gen_dev_entry(), "prop", copy.deepcopy(self.prop_name))

    def lookup_prop(self):
        dev = self.mach.id2node[self.dev_id]
        prop = dev.properties[self.prop_name]
        return prop

    def __read_set__(self):
        return MachineDeviceOperation.__read_set__(self) + \
            [ self.gen_dev_entry() ]

class MOp_DelDevProp(MachineDevicePropertyOperation):
    def __init__(self, *args, **kwargs):
        MachineDevicePropertyOperation.__init__(self, *args, **kwargs)

    def __backup__(self):
        prop = self.lookup_prop()

        self.prop_type = prop.prop_type
        self.prop_val = copy.deepcopy(prop.prop_val)

    def __do__(self):
        dev = self.mach.id2node[self.dev_id]
        del dev.properties[self.prop_name]

    def __undo__(self):
        prop = QOMPropertyValue(self.prop_type, self.prop_name, self.prop_val)

        dev = self.mach.id2node[self.dev_id]

        dev.properties.append(prop)

    def __write_set__(self):
        return MachineDevicePropertyOperation.__write_set__(self) + \
            [ self.gen_prop_entry() ]

class MOp_AddDevProp(MachineDeviceOperation):
    def __init__(self, prop, *args, **kw):
        MachineDeviceOperation.__init__(self, *args, **kw)

        self.prop_name = copy.deepcopy(prop.prop_name)
        self.prop_type = prop.prop_type
        self.prop_val = copy.deepcopy(prop.prop_val)

    def __backup__(self):
        pass

    def __do__(self):
        prop = QOMPropertyValue(self.prop_type, self.prop_name, self.prop_val)

        dev = self.mach.id2node[self.dev_id]

        dev.properties.append(prop)

    def __undo__(self):
        dev = self.mach.id2node[self.dev_id]
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
