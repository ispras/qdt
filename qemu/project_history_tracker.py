from common import \
    HistoryTracker

from machine_editing import \
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