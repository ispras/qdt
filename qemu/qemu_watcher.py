__all__ = [
    "MachineWatcher"
  , "PCMachineWatcher"
  , "QOMTreeReverser"
  , "MachineReverser"
]

from .runtime_qemu_model import (
    RQOMTree,
    RQObjectProperty,
    RQInstance
)
from .project_editing import (
    POp_AddDesc
)
from .machine_editing import (
    MOp_AddIRQHub,
    MOp_AddIRQLine,
    MOp_AddDevProp,
    MOp_SetDevProp,
    MOp_SetDevParentBus
)
from debug import (
    Watcher,
    TYPE_CODE_PTR
)
from common import (
    pypath,
    notifier,
    sort_topologically
)
from re import (
    compile
)
from graphviz import (
    Digraph
)
from inspect import (
    getmembers,
    ismethod
)
# use ours pyrsp
with pypath("..pyrsp"):
    from pyrsp.utils import (
        s
    )

# Characters disallowed in node ID according to DOT language. That is not a
# full list though.
# https://www.graphviz.org/doc/info/lang.html
re_DOT_ID_disalowed = compile(r"[^a-zA-Z0-9_]")


def gv_node(label):
    return re_DOT_ID_disalowed.sub("_", label)


class QOMTreeReverser(Watcher):
    """ Sets breakpoints on key places of QOM tree initialization and reverses
the QOM tree by fetching relevant data.
    """

    def __init__(self, dic, interrupt = True, verbose = False, **kw):
        """
    :param interrupt:
        Stop QEmu and exit `RemoteTarget.run` after QOM module is initialized.
        """
        super(QOMTreeReverser, self).__init__(dic,
            verbose = verbose,
            **kw
        )

        self.tree = RQOMTree()
        self.interrupt = interrupt

    def on_type_register_internal(self):
        # type_register_internal

        "object.c:139 v2.12.0"

        t = self.tree.account(self.rt["ti"])

        if self.verbose:
            print("%s -> %s" % (t.parent, t.name))

    def on_type_initialize(self):
        # now the type and its ancestors are initialized

        """ object.c:344 v2.12.0
            object.c:333 63f7b10bc552be8a2cd1da87e8b27f9a5a217b91
        """

        rt = self.rt
        type_impl = rt["ti"]

        ti_addr = type_impl.fetch_pointer()
        a2t = self.tree.addr2type

        if ti_addr not in a2t:
            # There are interfaces providing variations of regular types. They
            # do not path through type_register_internal because its `TypeInfo`
            # is created and used directly by type_initialize_interface.
            return

        t = a2t[ti_addr]

        if t.implements("device"):
            cls = type_impl["class"]

            dev_cls = cls.cast("DeviceClass *")
            realize_addr = dev_cls["realize"].fetch_pointer()

            if realize_addr:
                t.realize = rt.dic.subprogram(realize_addr)

    def on_main(self):
        # main, just after QOM module initialization

        """
            softmmu/vl.c:2867 bac068e0648c1f5c37f6a0a9423b8aa55e8c09c2
            vl.c:3075 v2.12.0
            vl.c:2980 d0dff238a87fa81393ed72754d4dc8b09e50b08b
        """

        if self.interrupt:
            self.rt.target.exit = True

    def to_file(self, dot_file_name):
        "Writes QOM tree to Graphviz file."

        graph = Digraph(
            name = "QOM",
            graph_attr = dict(
                rankdir = "LR"
            ),
            node_attr = dict(
                shape = "polygon",
                fontname = "Momospace"
            ),
            edge_attr = dict(
                style = "filled"
            ),
        )

        for t in sort_topologically(
            v for v in self.tree.name2type.values() if v.parent is None
        ):
            n = gv_node(t.name)
            label = t.name + "\\n0x%x" % t.impl.address
            if t.instance_casts:
                label += "\\n*"
                for cast in t.instance_casts:
                    label += "\\n" + s(cast.name)

            graph.node(n, label = label)
            if t.parent:
                graph.edge(gv_node(t.parent), n)

        with open(dot_file_name, "w") as f:
            f.write(graph.source)


@notifier(
    "machine_created", # RQInstance
    "device_creating", # RQInstance
    "device_created", # RQInstance
    "bus_created", # RQInstance
    "bus_attached", # RQInstance bus, RQInstance device
    "device_attached", # RQInstance device, RQInstance bus
    "property_added", # RQInstance, RQObjectProperty
    "property_set", # RQInstance, RQObjectProperty, Value
    "irq_connected", # RQInstance
    "irq_split_created", # RQInstance (IRQ)
)
class MachineWatcher(Watcher):
    """ Watches machine initialization by setting breakpoints at key points of
corresponding QEmu API. It remembers instances composing the machine.
Notifications are issued for many machine composition events.
    """

    def __init__(self, dic, qom_tree,
        interrupt = False,
        **kw
    ):
        """
    :type qom_tree: RQOMTree

    :param interrupt:
        Interrupt QEmu process after machine is fully created.

        """
        super(MachineWatcher, self).__init__(dic,
            **kw
        )
        self.tree = qom_tree
        # addr -> RQInstance mapping
        self.instances = {}
        self.machine = None
        self.interrupt = interrupt

    def account_instance(self, obj, type_impl = None):
        """
    :type obj: debug.Value
    :param obj:
        is runtime variable representing that instance

    :type type_impl: debug.Value
    :param type_impl:
        represents `TypeImpl` struct of QOM type that instance, if it has been
        already evaluated, an optimization

        """
        if obj.type.code == TYPE_CODE_PTR:
            obj = obj.dereference()
        if not obj.is_global:
            obj = obj.to_global()

        if type_impl is None:
            type_impl = obj.cast("Object")["class"]["type"]

        addr = type_impl.fetch_pointer()
        rqom_type = self.tree.addr2type[addr]

        i = RQInstance(obj, rqom_type)
        self.instances[obj.address] = i

        # propagate class properties to the instance
        for t in rqom_type.iter_inheritance():
            for prop in t.properties:
                i.properties[prop.name] = RQObjectProperty(i, prop.prop,
                    name = prop.name,
                    _type = prop.type
                )
                self.__notify_property_added(i, prop)

        return i

    # Breakpoint handlers

    def on_obj_init_start(self):
        # object_initialize_with_type, before `object_init_with_type`

        """
            object.c:513 v5.1.0
            object.c:384 v2.12.0
            object.c:376 63f7b10bc552be8a2cd1da87e8b27f9a5a217b91
        """

        machine = self.machine
        if machine is None:
            return

        rt = self.rt
        impl = rt["type"]
        t = self.tree[impl.fetch_pointer()]

        inst = self.account_instance(rt["obj"], impl)
        inst.relate(machine)

        if t.implements("device"):
            if self.verbose:
                print("Creating device " + inst.type.name)
            self.current_device = inst

            self.__notify_device_creating(inst)
        elif t.implements("qemu:memory-region"):
            if self.verbose:
                print("Creating memory")
            self.current_memory = inst

    def on_obj_init_end(self):
        # object_initialize_with_type, return

        """ object.c:386 v2.12.0
            object.c:378 63f7b10bc552be8a2cd1da87e8b27f9a5a217b91
        """

        if self.machine is None:
            return

        rt = self.rt
        addr = rt["obj"].fetch_pointer()

        inst = self.instances[addr]

        if inst.type.implements("device"):
            self.__notify_device_created(inst)

    def on_board_init_start(self):
        # machine_initfn

        """
            hw/core/machine.c:819 11bc4a13d1f4b07dafbd1dda4d4bf0fdd7ad65f2
                First line of machine_initfn

            hw/core/machine.c:656 b2fc91db84470a78f8e93f5b5f913c17188792c8
            hw/core/machine.c:654 v2.12.0
        """

        self.machine = inst = self.account_instance(self.rt["ms"])

        desc = inst.type.impl["class"].cast("MachineClass*")["desc"]

        self.__notify_machine_created(inst)

        if not self.verbose:
            return

        print("Machine creation started\nDescription: " +
            desc.fetch_c_string()
        )

    def on_mem_init_end(self):
        # return from memory_region_init

        """
            memory.c:1171 64a7b8de42aff54dce4d82585f25060a741531d1
            memory.c:1153 v2.12.0
            memory.c:1009 0ab8ed18a6fe98bfc82705b0f041fbf2a8ca5b60
            memory.c:930 v2.5.0
        """

        if self.machine is None:
            return

        rt = self.rt
        m = self.current_memory

        if m.obj.address != rt["mr"].fetch_pointer():
            raise RuntimeError("Unexpected memory initialization sequence")

        m.name = rt["name"].fetch_c_string()
        m.size = rt["size"].fetch(8)

        if not self.verbose:
            return
        print("Memory: %s 0x%x" % (m.name or "[nameless]", m.size))

    def on_board_init_end(self):
        # machine_run_board_init

        """
            hw/core/machine.c:1135 v5.2.0
                Last line in machine_run_board_init
                Just after machine_class->init(machine);

            hw/core/machine.c:830 v2.12.0 1
            vl.c:4476 ad584d37f2a86b392c25f3f00cc1f1532676c2d1 1
            vl.c:4510 2ae45973d61070c1a1883c1f3c43f7154cc85a91
        """

        self.remove_breakpoints()
        if self.interrupt:
            self.rt.target.exit = True

        if not self.verbose:
            return

        print("Machine creation ended: " +
            # explicit casting is not required here, it's just for testing
            self.machine.type.impl.cast("TypeImpl")["name"].fetch_c_string()
        )

    def on_obj_prop_add(self):
        # object_property_add, before insertion to prop. table; property found
        # Do NOT set this breakpoint on `return` because it will catch all
        # `return` statements in the function.

        """ object.c:975 v2.12.0
            object.c:954 63f7b10bc552be8a2cd1da87e8b27f9a5a217b91
        """

        if self.machine is None:
            return

        rt = self.rt
        obj = rt["obj"]
        obj_addr = obj.fetch_pointer()

        try:
            inst = self.instances[obj_addr]
        except KeyError:
            print("Skipping property for unaccounted object 0x%x of type"
                  " %s" % (
                    obj_addr,
                    obj["class"]["type"]["name"].fetch_c_string()
                )
            )
            return

        prop = inst.account_property(rt["prop"])

        self.__notify_property_added(inst, prop)

        if not self.verbose:
            return

        print("Object 0x%x (%s) -> %s (%s)" % (
            prop.owner.obj.address,
            prop.owner.type.name,
            prop.name,
            prop.type
        ))

    def on_obj_class_prop_add(self):
        # object_class_property_add, before insertion to prop. table;

        """
            object.c:1233 v5.1.0
            object.c:1152 a9b305ba291fb74f7ff732b3d7b8f4c812431ddf
        """

        rt = self.rt
        type_addr = rt["klass"]["type"].fetch_pointer()
        prop = rt["prop"]

        prop = prop.dereference()
        prop = prop.to_global()

        ct = self.tree.addr2type[type_addr]
        # This code assumes that no class property is added after at least one
        # instance has been created. Because all class properties are added
        # during class initialization.
        ct.properties.append(RQObjectProperty(ct, prop))

    def on_obj_prop_set(self):
        # object_property_set (prop. exists and has a setter)

        """
            object.c:1349 v5.1.0
            object.c:1122 v2.12.0
            object.c:1094 63f7b10bc552be8a2cd1da87e8b27f9a5a217b91
            object.c:1021 v2.5.0
        """

        if self.machine is None:
            return

        rt = self.rt
        obj_addr = rt["obj"].fetch_pointer()
        name = rt["name"].fetch_c_string()
        try:
            inst = self.instances[obj_addr]
        except:
            print("Skipping value of property '%s' for unaccounted object"
                " 0x%x" % (name, obj_addr)
            )
            return

        prop = inst.properties[name]

        self.__notify_property_set(inst, prop, None)

        if not self.verbose:
            return

        print("Object 0x%x (%s) -> %s (%s) = 0x%x (Visitor)" % (
            prop.owner.obj.address,
            prop.owner.type.name,
            prop.name,
            prop.type,
            rt["v"].fetch_pointer()
        ))

    def on_qbus_realize(self):
        # qbus_realize, parent may be NULL

        """
            hw/core/bus.c:122 d2623129a7dec1d3041ad1221dda1ca49c667532
            hw/core/bus.c:101 v2.12.0
            hw/core/qdev.c:716 v2.5.0
        """

        rt = self.rt
        bus = rt["bus"]

        bus_inst = self.instances[bus.fetch_pointer()]

        name = bus["name"].fetch_c_string()

        bus_inst.name = name

        self.__notify_bus_created(bus_inst)

        dev_addr = rt["parent"].fetch_pointer()
        if dev_addr:
            device_inst = self.instances[dev_addr]
            bus_inst.parent = device_inst
            device_inst.children.append(bus_inst)

            bus_inst.relate(device_inst)

            self.__notify_bus_attached(bus_inst, device_inst)

        if not self.verbose:
            return

        if dev_addr:
            print("Device 0x%x (%s) |----- bus 0x%s %s (%s)" % (
                device_inst.obj.address,
                device_inst.type.name,
                bus_inst.obj.address,
                bus_inst.name,
                bus_inst.type.name
            ))
        else:
            print("   ~-- bus 0x%s %s (%s)" % (
                bus_inst.obj.address,
                bus_inst.name,
                bus_inst.type.name
            ))

    def on_bus_unparent(self):
        # bus_unparent, before actual unparenting

        """
            hw/core/bus.c:118 v4.1.0
            hw/core/bus.c:123 v2.12.0
            hw/core/qdev.c:737 v2.5.0
        """

        # TODO: this code is not tested because this event never happens
        rt = self.rt
        bus = rt["bus"]
        bus_inst = self.instances[bus.fetch_pointer()]
        parent = bus["parent"]
        device_inst = self.instances[parent.fetch_pointer()]

        bus_inst.parent = None
        device_inst.children.remove(bus_inst)

        device_inst.unrelate(bus_inst)

        if not self.verbose:
            return

        print("Device 0x%x (%s) |-x x- bus 0x%s %s (%s)" % (
            device_inst.obj.address,
            device_inst.type.name,
            bus_inst.obj.address,
            bus_inst.name,
            bus_inst.type.name
        ))

    def on_bus_add_child(self):
        # bus_add_child, entry point

        """
            hw/core/qdev.c:75 12b2e9f30f978f26f35f9df5c2ef96fbc019bab6
            hw/core/qdev.c:73 v2.12.0
            hw/core/qdev.c:101 67980031d234aa90524b83bb80bb5d1601d29076
        """

        rt = self.rt
        bus = rt["bus"]
        bus_inst = self.instances[bus.fetch_pointer()]
        device_inst = self.instances[rt["child"].fetch_pointer()]

        device_inst.parent = bus_inst
        bus_inst.children.append(device_inst)
        bus_inst.relate(device_inst)

        self.__notify_device_attached(device_inst, bus_inst)

        if not self.verbose:
            return

        print("Bus 0x%x %s (%s) |----- device 0x%x (%s)" % (
            bus_inst.obj.address,
            bus_inst.name,
            bus_inst.type.name,
            device_inst.obj.address,
            device_inst.type.name
        ))

    def on_bus_remove_child(self):
        # bus_remove_child, before actual unparenting

        # v2.12.0
        """
            hw/core/qdev.c:66 v5.2.0
                Just after the child (`kid`) is found in `children` list.

            hw/core/qdev.c:57 v2.12.0
            hw/core/qdev.c:70 67980031d234aa90524b83bb80bb5d1601d29076
        """

        print("not implemented")

    def on_qdev_get_gpio_in_named(self):
        # qdev_get_gpio_in_named, return

        """ core/qdev.c:456 v2.12.0
            core/qdev.c:473 67980031d234aa90524b83bb80bb5d1601d29076
        """

        instances = self.instances
        rt = self.rt

        irq_addr = rt.returned_value.fetch_pointer()
        dst_addr = rt["dev"].fetch_pointer()
        dst_name = rt["name"].fetch_c_string()
        dst_idx = rt["n"].fetch(4) # int

        irq = instances[irq_addr]
        dst = instances[dst_addr]

        irq.dst = (dst, dst_name, dst_idx)

        self.check_irq_connected(irq)

    def on_qdev_connect_gpio_out_named(self):
        # qdev_connect_gpio_out_named, after IRQ was assigned and before
        # property name `propname` freed.

        """
            core/qdev.c:535 v5.1.0
            core/qdev.c:479 v2.12.0
            core/qdev.c:496 67980031d234aa90524b83bb80bb5d1601d29076
        """

        rt = self.rt

        irq_addr = rt["pin"].fetch_pointer()

        if not irq_addr:
            return

        instances = self.instances

        src_addr = rt["dev"].fetch_pointer()
        src_name = rt["name"].fetch_c_string()
        src_idx = rt["n"].fetch(4) # int

        src = instances[src_addr]
        irq = instances[irq_addr]

        irq.src = (src, src_name, src_idx)

        self.check_irq_connected(irq)

    def check_irq_connected(self, irq):
        src = irq.src
        dst = irq.dst

        if src is None or dst is None:
            return

        self.__notify_irq_connected(irq)

    def on_qemu_irq_split(self):
        # returning from `qemu_irq_split`

        """
            core/irq.c:121 fc531e7cab1ce598a9b994155b8adb805084cb0f
            core/irq.c:122 v2.12.0
            core/irq.c:121 67980031d234aa90524b83bb80bb5d1601d29076
        """

        rt = self.rt
        instances = self.instances

        split_irq_addr = rt.returned_value.fetch_pointer()

        split_irq = instances[split_irq_addr]

        self.__notify_irq_split_created(split_irq)

        irq1 = instances[rt["irq1"].fetch_pointer()]
        irq2 = instances[rt["irq2"].fetch_pointer()]

        split_irq.dst = (split_irq, None, 0) # yes, to itself
        irq1.src = (split_irq, None, 0)
        irq2.src = (split_irq, None, 1)

        self.check_irq_connected(irq1)
        self.check_irq_connected(irq2)


class PCMachineWatcher(MachineWatcher):
    """ Support for non-standard IRQ creation of PC i440fx based machines
(Global Signaling Interrupts).
    """

    def on_pc_piix_gsi(self):

        "pc_piix.c:301 v2.12.0 1"

        rt = self.rt
        instances = self.instances

        gsi = rt["pcms"]["gsi"]
        # gsi is array of qemu_irq
        gsi_state = rt["gsi_state"]
        i8259_irq = gsi_state["i8259_irq"]
        ioapic_irq = gsi_state["ioapic_irq"]

        for i in range(24): # GSI_NUM_PINS, IOAPIC_NUM_PINS
            gsi_addr = gsi[i].fetch_pointer()
            gsi_inst = instances[gsi_addr]

            self._MachineWatcher__notify_irq_split_created(gsi_inst)
            # yes, to itself, like a split irq
            gsi_inst.dst = (gsi_inst, None, 0)
            self.check_irq_connected(gsi_inst)

            ioapic_irq_addr = ioapic_irq[i].fetch_pointer()
            if ioapic_irq_addr != 0:
                ioapic_inst = instances[ioapic_irq_addr]

                ioapic_inst.src = (gsi_inst, None, i)
                self.check_irq_connected(ioapic_inst)

            if i < 16: # ISA_NUM_IRQS
                i8259_irq_addr = i8259_irq[i].fetch_pointer()
                if i8259_irq_addr != 0:
                    i8259_inst = instances[i8259_irq_addr]

                    i8259_inst.src = (gsi_inst, None, i)
                    self.check_irq_connected(i8259_inst)

    def on_piix4_pm_gsi(self):
        # return from piix4_pm_init
        """
            acpi/piix4.c:539 v5.1.0
            acpi/piix4.c:578 v2.12.0
        """

        rt = self.rt

        irq_addr = rt["sci_irq"].fetch_pointer()
        src_addr = rt["dev"].fetch_pointer()

        src = self.instances[src_addr]
        irq = self.instances[irq_addr]

        irq.src = (src, None, None)

        self.check_irq_connected(irq)


class CastCatcher(object):
    """ A breakpoint handler that inspects all subprogram pointers those do
refer to a given QOM instance and remembers types of those pointers as
possible casts for instances of that QOM type.
    """

    def __init__(self, instance, runtime = None):
        self.inst = instance
        self.rt = runtime

    def __call__(self):
        inst = self.inst
        obj = inst.obj

        addr = obj.address
        qom_type = inst.type

        rt = self.rt
        if rt is None:
            rt = obj.runtime
        if rt is None:
            raise ValueError("Cannot obtain runtime")

        for datum_name in rt.subprogram.data:
            datum = rt[datum_name]
            datum_type = datum.type
            if datum_type.code != TYPE_CODE_PTR:
                continue
            datum_addr = datum.fetch_pointer()
            if datum_addr != addr:
                continue
            qom_type.instance_casts.add(datum_type.target_type)


class MachineReverser(object):
    """ Listener for `MachineWatcher` that reconstructs machine as a
description for QDT project.
    """

    def __init__(self, watcher, tracker):
        """
    :type watcher: MachineWatcher
    :type tracker: GUIProjectHistoryTracker
        """
        self.watcher = watcher
        self.tracker = tracker

        # auto assign event handlers
        for name, ref in getmembers(self):
            if name[:4] == "_on_" and ismethod(ref):
                watcher.watch(name[4:], getattr(self, name))

        self.__next_node_id = 1
        self.inst2id = {}
        self.irq_inst2hub_id = {}
        self.id2inst = []

    def __id(self):
        _id = self.__next_node_id
        self.__next_node_id += 1
        return _id

    def _on_runtime_set(self, rt):
        self.rt = rt
        self.target = rt.target

    def _on_machine_created(self, m):
        tracker = self.tracker
        tracker.stage(POp_AddDesc, "MachineNode",
            tracker.p.next_serial_number(),
            name = m.type.name,
            directory = ""
        )
        tracker.commit()

        self.machine = machine = tracker.p.find1(name = m.type.name)
        self.proxy = tracker.get_machine_proxy(machine)

    def _on_device_creating(self, inst):
        _id = self.__id()
        self.inst2id[inst] = _id
        self.id2inst.append(inst)

        _type = inst.type
        if _type.implements("pci-device"):
            self.proxy.add_device("PCIExpressDeviceNode", _id,
                qom_type = _type.name
            )
        elif _type.implements("sys-bus-device"):
            self.proxy.add_device("SystemBusDeviceNode", _id,
                qom_type = _type.name
            )
        else:
            self.proxy.add_device("DeviceNode", _id,
                qom_type = _type.name
            )

        self.proxy.commit()

        target = self.target
        rt = self.rt
        cc = CastCatcher(inst)

        ii = _type.instance_init
        if ii:
            for addr in ii.epilogues:
                rt.add_br(target.reg_fmt % addr, cc)

        realize = _type.realize
        if realize:
            for addr in realize.epilogues:
                rt.add_br(target.reg_fmt % addr, cc)

    def _on_bus_created(self, bus):
        _id = self.__id()
        self.inst2id[bus] = _id
        self.id2inst.append(bus)

        bus_type = bus.type
        if bus_type.implements("System"):
            bus_class = "SystemBusNode"
        elif bus_type.implements("PCI"):
            bus_class = "PCIExpressBusNode"
        elif bus_type.implements("ISA"):
            bus_class = "ISABusNode"
        elif bus_type.implements("IDE"):
            bus_class = "IDEBusNode"
        elif bus_type.implements("i2c-bus"):
            bus_class = "I2CBusNode"
        else:
            bus_class = "BusNode"

        self.proxy.add_bus(bus_class, _id)
        self.proxy.commit()

    def _on_bus_attached(self, bus, device):
        bus_id = self.inst2id[bus]
        device_id = self.inst2id[device]

        self.proxy.append_child_bus(device_id, bus_id)
        self.proxy.commit()

    def _on_device_attached(self, device, bus):
        bus_id = self.inst2id[bus]
        device_id = self.inst2id[device]

        self.proxy.stage(MOp_SetDevParentBus, self.machine.id2node[bus_id],
            device_id
        )
        self.proxy.commit()

    def _on_property_added(self, obj, _property):
        prop = _property.prop
        setter_addr = prop["set"].fetch_pointer()

        if not setter_addr:
            return

        inst2id = self.inst2id
        if obj not in inst2id:
            return

        if not obj.type.implements("device"):
            return

        self.proxy.stage(MOp_AddDevProp, _property.as_qom, inst2id[obj])
        self.proxy.commit()

    def _on_property_set(self, obj, _property, val):
        prop = _property.prop
        setter_addr = prop["set"].fetch_pointer()

        if not setter_addr:
            return

        inst2id = self.inst2id
        if obj not in inst2id:
            return

        if not obj.type.implements("device"):
            return

        qom_prop = _property.as_qom

        self.proxy.stage(MOp_SetDevProp, qom_prop.prop_type,
            qom_prop.prop_val, # TODO: recover from `val`
            qom_prop,
            inst2id[obj]
        )
        self.proxy.commit()

    def _on_irq_connected(self, irq):
        i2i = self.inst2id

        _id = self.__id()
        i2i[irq] = _id
        self.id2inst.append(irq)

        src = irq.src
        dst = irq.dst

        src_inst = src[0]
        dst_inst = dst[0]

        ii2hi = self.irq_inst2hub_id

        # A split IRQ (hub) instance presents in both mappings. But in
        # `irq_inst2hub_id` it points to IRQ hub id while in `inst2id` it
        # points to IRQ line id
        if src_inst in ii2hi:
            src_id = ii2hi[src_inst]
        else:
            src_id = i2i[src_inst]

        if dst_inst in ii2hi:
            dst_id = ii2hi[dst_inst]
        else:
            dst_id = i2i[dst_inst]

        self.proxy.stage(MOp_AddIRQLine,
            src_id, dst_id,
            src[2], dst[2], # indices
            src[1], dst[1],  # names
            _id
        )
        self.proxy.commit()

    def _on_irq_split_created(self, irq):
        _id = self.__id()
        self.irq_inst2hub_id[irq] = _id
        self.id2inst.append(irq)

        self.proxy.stage(MOp_AddIRQHub, _id)
        self.proxy.commit()
