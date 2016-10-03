from common import \
    HistoryTracker

from machine_editing import \
    MOp_AddBus, \
    MOp_DelBus, \
    MOp_SetChildBus, \
    MOp_SetDevParentBus, \
    MOp_DelIRQLine, \
    MOp_DelIRQHub

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

    def delete_bus(self, bus_id):
        bus = self.mach.id2node[bus_id]

        if bus.parent_device:
            parent_id = bus.parent_device.id

            # Deleting child bus involves shifting of consequent buses indexes.
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

        for child in bus.devices:
            self.stage(MOp_SetDevParentBus, None, child.id)

        self.stage(MOp_DelBus, bus.id)

    def __getattr__(self, name):
        if name in [ 
            "stage",
            "delete_irq_line",
            "delete_irq_hub"
        ]:
            return MachineProxyTracker.stage
        else:
            return getattr(self.pht, name)

class ProjectHistoryTracker(HistoryTracker):
    def __init__(self, project, *args, **kw):
        HistoryTracker.__init__(self, *args, **kw)
        self.p = project

    def stage(self, op_class, *op_args, **op_kw):
        return HistoryTracker.stage(self,
            op_class,
            *(op_args + (self.p,)), **op_kw
        )

    def get_machine_proxy(self, machine_description):
        return MachineProxyTracker(self, machine_description)