from common import (
    get_default_args,
    HistoryTracker
)
from .machine_editing import (
    MOp_SetMemNodeAttr,
    MOp_RemoveMemChild,
    MOp_AddMemoryNode,
    MOp_DelMemoryNode,
    MOp_SetDevProp,
    MOp_DelDevProp,
    MOp_DelIOMapping,
    MOp_AddDevice,
    MOp_DelDevice,
    MOp_AddBus,
    MOp_DelBus,
    MOp_SetChildBus,
    MOp_SetDevParentBus,
    MOp_DelIRQLine,
    MOp_DelIRQHub
)
from .machine_nodes import (
    MemoryAliasNode,
    DeviceNode,
    BusNode,
    IRQHub,
    IRQLine,
    MemoryNode,
    QOMPropertyTypeLink,
    SystemBusDeviceNode
)
from .machine_description import (
    MachineNode
)
from .project_editing import (
    POp_DelDesc
)
from common import (
    mlget as _
)

class MachineProxyTracker(object):
    def __init__(self, project_history_tracker, machine_description):
        self.pht = project_history_tracker
        self.mach = machine_description

    def stage(self, op_class, *op_args, **op_kw):
        return self.pht.stage(
            op_class,
            *(op_args + (self.mach.__sn__,)),
            **op_kw
        )

    def delete_irq_line(self, line_id):
        self.stage(MOp_DelIRQLine, line_id)

        self.set_sequence_description(_("Delete IRQ line."))

    def delete_irq_hub(self, hub_id):
        hub = self.mach.id2node[hub_id]
        for irq in hub.irqs:
            self.delete_irq_line(irq.id)
        self.stage(MOp_DelIRQHub, hub_id)

        self.set_sequence_description(_("Delete IRQ hub."))

    def add_bus(self, bus_class_name, new_id, **bus_arguments):
        self.stage(MOp_AddBus, bus_class_name, new_id,
            **bus_arguments)

        self.set_sequence_description(_("Add bus."))

    def append_child_bus(self, dev_id, bus_id):
        bus = self.mach.id2node[bus_id]

        if bus.parent_device:
            self.disconnect_child_bus(bus_id)

        dev = self.mach.id2node[dev_id]

        self.stage(MOp_SetChildBus, dev_id, len(dev.buses), bus_id)

        self.set_sequence_description(_("Connect bus to controller."))

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

        self.set_sequence_description(_("Disconnect bus from controller."))

    def delete_bus(self, bus_id):
        bus = self.mach.id2node[bus_id]

        if bus.parent_device:
            self.disconnect_child_bus(bus_id)

        for child in bus.devices:
            self.stage(MOp_SetDevParentBus, None, child.id)

        self.stage(MOp_DelBus, bus.id)

        self.set_sequence_description(_("Delete bus."))

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

        """ If propery of other device is link to the device then set the
        property to -1 """
        for other_dev in self.mach.devices:
            if other_dev is dev:
                # Self-linking properties of the device is already deleted
                continue

            for prop in other_dev.properties:
                if prop.prop_type is QOMPropertyTypeLink:
                    if prop.prop_val is dev:
                        self.stage(MOp_SetDevProp, QOMPropertyTypeLink, None,
                            prop, other_dev.id
                        )

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

        self.set_sequence_description(_("Delete device."))

    def add_device(self, class_name, new_id, **device_arguments):
        default_qom_type = "TYPE_DEVICE"
        if class_name == "SystemBusDeviceNode":
            default_qom_type = "TYPE_SYS_BUS_DEVICE"
        elif class_name == "PCIExpressDeviceNode":
            default_qom_type = "TYPE_PCI_DEVICE"

            if "slot" not in device_arguments:
                device_arguments["slot"] = 0

            if "function" not in device_arguments:
                device_arguments["function"] = 0

        if "qom_type" not in device_arguments:
            device_arguments["qom_type"] = default_qom_type

        self.stage(MOp_AddDevice, class_name, new_id, **device_arguments)

        self.set_sequence_description(_("Add device."))

    def remove_memory_child(self, parent_id, child_id):
        parent = self.mach.id2node[parent_id]
        child = self.mach.id2node[child_id]

        """ Generate operations reverting child setting to defaults. Reverting
        the operation restores child settings. """

        add_child_args = get_default_args(parent.__class__.add_child)
        for arg_name, arg_val in add_child_args.items():
            if getattr(child, arg_name) != arg_val:
                self.stage(MOp_SetMemNodeAttr, arg_name,
                    arg_val, child_id)

        self.stage(MOp_RemoveMemChild, child_id, parent_id)

        self.set_sequence_description(_("Exclude memory region."))

    def add_memory_node(self, class_name, new_id, **memory_arguments):
        class2str = {
           "MemoryNode": "Container",
           "MemorySASNode": "System address space",
           "MemoryAliasNode": "Alias",
           "MemoryRAMNode": "RAM",
           "MemoryROMNode": "ROM"
        }

        if "name" not in memory_arguments:
            memory_arguments["name"] = class2str[class_name];

        if "MemorySASNode" not in class_name and "size" not in memory_arguments:
            memory_arguments["size"] = 0xFEED;

        self.stage(MOp_AddMemoryNode, class_name, new_id, **memory_arguments)

        self.set_sequence_description(_("Add memory node."))

    def delete_memory_node(self, m_id):
        mem = self.mach.id2node[m_id]

        # delete all aliases to the memory node
        # Copy list to avoid runtime error on dict changed during iteration.
        for n in list(self.mach.id2node.values()):
            if isinstance(n, MemoryAliasNode):
                if n.alias_to is mem:
                    self.delete_memory_node(n.id)

        # commit all deletions because they could change children of mem
        self.commit(new_sequence = False)

        for child in mem.children:
            self.remove_memory_child(m_id, child.id)

        if mem.parent is not None:
            self.remove_memory_child(mem.parent.id, m_id)

        # set properties linking to the memory node to linking nothing
        for n in self.mach.id2node.values():
            if not isinstance(n, DeviceNode):
                continue

            for p in n.properties:
                if  not p.prop_type is QOMPropertyTypeLink \
                or  not p.prop_val is mem :
                    continue

                self.stage(MOp_SetDevProp, QOMPropertyTypeLink, None, p, n.id)

        self.stage(MOp_DelMemoryNode, m_id)
        self.set_sequence_description(_("Delete memory region."))

    def delete_ids(self, node_ids):
        for node_id in node_ids:
            try:
                n = self.mach.id2node[node_id]
            except KeyError:
                # The node was removed by one of previously called helper
                continue

            if isinstance(n, DeviceNode):
                self.delete_device(node_id)
            elif isinstance(n, BusNode):
                self.delete_bus(node_id)
            elif isinstance(n, IRQHub):
                self.delete_irq_hub(node_id)
            elif isinstance(n, IRQLine):
                self.delete_irq_line(node_id)
            elif isinstance(n, MemoryNode):
                self.delete_memory_node(n.id)
            else:
                raise Exception(
"No helper for deletion of node %d of type %s was defined" % \
(n.id, type(n).__name__)
                )

            self.pht.commit(new_sequence = False)

        self.set_sequence_description(_("Delete set of machine nodes."))

    def __getattr__(self, name):
        return getattr(self.pht, name)

class ProjectHistoryTracker(HistoryTracker):
    def __init__(self, project, *args, **kw):
        HistoryTracker.__init__(self, *args, **kw)
        self.p = project

        ops = self.get_branch()
        last_seq = ops[-1].seq

        if last_seq is None:
            last_seq = 0
            for op in ops:
                op.seq = 0

        self.current_sequence = last_seq + 1

        self.new_sequence = True

    def stage(self, op_class, *op_args, **op_kw):
        self.new_sequence = True
        op_kw["sequence"] = self.current_sequence

        return HistoryTracker.stage(self,
            op_class,
            *(op_args + (self.p,)), **op_kw
        )

    # explicitly attach consequent staged operation to new sequence
    def start_new_sequence(self):
        if self.new_sequence:
            self.new_sequence = False
            self.current_sequence += 1

    def get_machine_proxy(self, machine_description):
        return MachineProxyTracker(self, machine_description)

    """
    new_sequence - begin new sequence after committing staged operation
        (True by default)
    """
    def commit(self, *args, **kw):
        try:
            ns = kw["new_sequence"]
        except KeyError:
            ns = True
        else:
            del kw["new_sequence"]

        HistoryTracker.commit(self, *args, **kw)

        if ns:
            self.start_new_sequence()

    def delete_description(self, desc):
        if isinstance(desc, MachineNode):
            # first delete all content of machine
            mht = MachineProxyTracker(self, desc)
            mht.delete_ids(list(desc.id2node.keys()))

        self.stage(POp_DelDesc, desc.__sn__)
        self.set_sequence_description(_("Delete description '%s'.") % desc.name)
