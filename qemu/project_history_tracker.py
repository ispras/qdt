from common import \
    HistoryTracker

from machine_editing import \
    MOp_DelDevProp, \
    MOp_DelIOMapping, \
    MOp_AddDevice, \
    MOp_DelDevice, \
    MOp_AddBus, \
    MOp_DelBus, \
    MOp_SetChildBus, \
    MOp_SetDevParentBus, \
    MOp_DelIRQLine, \
    MOp_DelIRQHub

from machine_description import \
    SystemBusDeviceNode

class MachineProxyTracker(object):
    def __init__(self, project_history_tracker, machine_description):
        self.pht = project_history_tracker
        self.mach = machine_description

    def stage(self, op_class, *op_args, **op_kw):
        return self.pht.stage(
            op_class,
            *(op_args + (self.mach,)),
            **op_kw
        )

    def delete_irq_line(self, line_id):
        return self.stage(MOp_DelIRQLine, line_id)

    def delete_irq_hub(self, hub_id):
        hub = self.mach.id2node[hub_id]
        for irq in hub.irqs:
            self.delete_irq_line(irq.id)
        self.stage(MOp_DelIRQHub, hub_id)

    def add_bus(self, bus_class_name, new_id, **bus_arguments):
        self.stage(MOp_AddBus, bus_class_name, new_id,
            **bus_arguments)

    def append_child_bus(self, dev_id, bus_id):
        bus = self.mach.id2node[bus_id]

        if bus.parent_device:
            self.disconnect_child_bus(bus_id)

        dev = self.mach.id2node[dev_id]

        self.stage(MOp_SetChildBus, dev_id, len(dev.buses), bus_id)

    def disconnect_child_bus(self, bus_id):
        bus = self.mach.id2node[bus_id]

        parent_id = bus.parent_device.id

        # Child bus disconnecting involves shifting of consequent buses indexes.
        # The only currently available way is to disconnect tail buses,
        # disconnect the bus, reconnect tail buses again with decremented
        # indexes

        temporally_disconnected = []

        for idx, b in reversed(
            [ x for x in enumerate(bus.parent_device.buses) ]
        ):
            if b.id == bus_id:
                self.stage(MOp_SetChildBus, parent_id, idx, -1)
                for jdx, bus_id in temporally_disconnected:
                    self.stage(MOp_SetChildBus, parent_id, jdx - 1, bus_id)
                break
            else:
                temporally_disconnected.insert(0, (idx, b.id))
                self.stage(MOp_SetChildBus, parent_id, idx, -1)

    def delete_bus(self, bus_id):
        bus = self.mach.id2node[bus_id]

        if bus.parent_device:
            self.disconnect_child_bus(bus_id)

        for child in bus.devices:
            self.stage(MOp_SetDevParentBus, None, child.id)

        self.stage(MOp_DelBus, bus.id)

    def delete_base_device(self, dev_id):
        dev = self.mach.id2node[dev_id]

        if not dev.parent_bus is None:
            self.stage(MOp_SetDevParentBus, None, dev_id)

        for idx in reversed(range(len(dev.buses))):
            self.stage(MOp_SetChildBus, dev_id, idx, -1)

        for irq in dev.irqs:
            self.stage(MOp_DelIRQLine, irq.id)

        for prop in dev.properties:
            self.stage(MOp_DelDevProp, prop, dev_id)

        self.stage(MOp_DelDevice, dev_id)

    def delete_system_bus_device(self, dev_id):
        dev = self.mach.id2node[dev_id]

        for mio in [ "pmio", "mmio" ]:
            for idx in reversed(
                range(len(getattr(dev, mio + "_mappings")))
            ):
                self.stage(MOp_DelIOMapping, mio, idx, dev_id)

        self.delete_base_device(dev_id)

    def delete_device(self, dev_id):
        dev = self.mach.id2node[dev_id]

        if isinstance(dev, SystemBusDeviceNode):
            self.delete_system_bus_device(dev_id)
        else:
            self.delete_base_device(dev_id)

    def __getattr__(self, name):
        return getattr(self.pht, name)

class ProjectHistoryTracker(HistoryTracker):
    def __init__(self, project, *args, **kw):
        HistoryTracker.__init__(self, *args, **kw)
        self.p = project
        self.current_sequence = 0
        self.new_sequence = True

    def stage(self, op_class, *op_args, **op_kw):
        self.new_sequence = True
        op_kw["sequence"] = self.current_sequence

        return HistoryTracker.stage(self,
            op_class,
            *(op_args + (self.p,)), **op_kw
        )

    def get_machine_proxy(self, machine_description):
        return MachineProxyTracker(self, machine_description)

    def commit(self, *args, **kw):
        if self.new_sequence:
            self.new_sequence = False
            self.current_sequence += 1

        HistoryTracker.commit(self, *args, **kw)
