#!/usr/bin/python

from qemu import (
    MachineNode,
    MOp_AddIRQHub,
    MOp_AddIRQLine,
    MOp_AddDevProp,
    MOp_SetDevProp,
    MOp_SetDevParentBus,
    QOMPropertyTypeLink,
    QOMPropertyTypeString,
    QOMPropertyTypeBoolean,
    QOMPropertyTypeInteger,
    QOMPropertyValue
)
from collections import (
    defaultdict
)
from debug import (
    Runtime,
    InMemoryELFFile,
    DWARFInfoCache,
    Watcher,
    TYPE_CODE_PTR,
    GitLineVersionAdapter
)
from common import (
    mlget as _,
    pythonize,
    notifier,
    sort_topologically,
    lazy
)
from re import (
    compile
)
from graphviz import (
    Digraph
)
from socket import (
    socket,
    AF_INET,
    SOCK_STREAM
)
from argparse import (
    ArgumentParser
)
from sys import (
    stderr,
    path as python_path
)
from multiprocessing import (
    Process
)
from os import (
    remove,
    system
)
from inspect import (
    getmembers,
    ismethod
)
from widgets import (
    GUIProject,
    GUIProjectHistoryTracker,
    asksaveas,
    VarMenu,
    HotKey,
    HotKeyBinding,
    MachineDescriptionSettingsWidget,
    GUITk
)
from six.moves.tkinter_messagebox import (
    showerror
)
from traceback import (
    print_exc
)
from os.path import (
    split,
    join
)
# use ours pyrsp
python_path.insert(0, join(split(__file__)[0], "pyrsp"))

from pyrsp.targets import (
    AMD64
)

class RQOMTree(object):
    "QEmu object model tree descriptor at runtime"

    def __init__(self):
        self.name2type = {}
        self.addr2type = {}

        # Types are found randomly (i.e. not in parent-first order).
        self.unknown_parents = defaultdict(list)

    def account(self, impl, name = None, parent = None):
        """ Add a type.
    :type impl: debug.Value
    :param impl:
        is the value of type's `TypeImpl` struct
        """

        if impl.type.code == TYPE_CODE_PTR:
            # Pointer `impl` is definitely a value on the stack. It cannot be
            # used as a global. Same time `TypeImpl` is on the heap. Hence, it
            # can. I.e. a dereferenced `Value` should be used.
            impl = impl.dereference()
        if not impl.is_global:
            impl = impl.to_global()

        info_addr = impl.address

        t = RQOMType(self, impl, name = name, parent = parent)

        name = t.name
        parent = t.parent

        self.addr2type[info_addr] = t
        self.name2type[name] = t

        unk_p = self.unknown_parents

        n2t = self.name2type
        if parent in n2t:
            n2t[parent].children.append(t)
        else:
            unk_p[parent].append(t)

        if name in unk_p:
            t.children.extend(unk_p.pop(name))

        return t

    def __getitem__(self, addr_or_name):
        if isinstance(addr_or_name, str):
            return self.name2type[addr_or_name]
        else:
            return self.addr2type[addr_or_name]


class RQOMType(object):
    "QEmu object model type descriptor at runtime"

    def __init__(self, tree, impl, name = None, parent = None):
        """
    :type impl: debug.Value
    :param impl:
        is a global variable of type `TypeImpl`

    :type name: str
    :param name:
        is given if it is already known else it will be got from `impl`

    :type parent: str
    :param parent:
        is given if it is already known else it will be got from `impl`

        """
        self.tree = tree
        self.impl = impl
        if name is None:
            name = impl["name"].fetch_c_string()
        if parent is None:
            parent = impl["parent"].fetch_c_string()
            # Parent may be None
        self.name, self.parent = name, parent

        self.children = []

        # Instance pointer can be casted to different C types. Remember those
        # types.
        self.instance_casts = set()

        # "device"
        self.realize = None

    def instance_casts(self):
        """ A QOM instance can also be casted to C types those corresponds to
ancestors.
    :returns: list of possible casts (debug.Type)
        """
        ret = set(self.instance_casts)
        for a in self.iter_ancestors():
            for cast in a.instance_casts:
                ret.add(cast)
        return ret

    # TODO: there is too many boilerplate code for `TypeImpl` fields access.
    # Consider to rewrite it in a common way. `__getitem__` ?

    @lazy
    def instance_init(self):
        impl = self.impl

        addr = impl["instance_init"].fetch_pointer()
        if addr:
            return impl.dic.subprogram(addr)
        return None

    @lazy
    def class_init(self):
        impl = self.impl

        addr = impl["class_init"].fetch_pointer()
        if addr:
            return impl.dic.subprogram(addr)
        return None

    def __dfs_children__(self):
        return self.children

    def iter_ancestors(self):
        n2t = self.tree.name2type
        cur = self.parent

        while cur is not None:
            t = n2t[cur]
            yield t
            cur = t.parent

    def implements(self, name):
        if name == self.name:
            return True

        try:
            t = self.tree.name2type[name]
        except KeyError:
            # the type given is unknown, `self` cannot implement it
            return False

        for a in self.iter_ancestors():
            if a is t:
                return True
        return False


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

        # v2.12.0
        "object.c:139 4743c23509a51bd4ee85cc272287a41917d1be35"

        t = self.tree.account(self.rt["ti"])

        if self.verbose:
            print("%s -> %s" % (t.parent, t.name))

    def on_type_initialize(self):
        # now the type and its ancestors are initialized

        # v2.12.0
        """object.c:344 4743c23509a51bd4ee85cc272287a41917d1be35
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

        # v2.12.0
        """vl.c:3075 4743c23509a51bd4ee85cc272287a41917d1be35
vl.c:2980 d0dff238a87fa81393ed72754d4dc8b09e50b08b
"""

        if self.interrupt:
            self.rt.target.interrupt()

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
                    label += "\\n" + cast.name

            graph.node(n, label = label)
            if t.parent:
                graph.edge(gv_node(t.parent), n)

        with open(dot_file_name, "wb") as f:
            f.write(graph.source)


class RQObjectProperty(object):
    "Represents runtime state of QOM object property"

    def __init__(self, obj, prop, name = None, _type = None):
        """
    :type obj: RQInstance
    :param obj:
        is owner of that property
    :type prop: debug.Value
    :param prop:
        represents corresponding variable of type `ObjectProperty`
        """
        self.obj = obj
        self.prop = prop
        if name is None:
            name = prop["name"].fetch_c_string()
        if _type is None:
            _type = prop["type"].fetch_c_string()
        self.name = name
        self.type = _type

    @lazy
    def as_qom(self):
        "Converts to property model from `qemu` module."
        # XXX: note that returned values are not default
        t = self.type
        if t.startswith("int") or t.startswith("uint"):
            return QOMPropertyValue(QOMPropertyTypeInteger, self.name, 0)
        elif t.startswith("link<"):
            return QOMPropertyValue(QOMPropertyTypeLink, self.name, None)
        elif t == "bool":
            return QOMPropertyValue(QOMPropertyTypeBoolean, self.name, False)
        else:
            return QOMPropertyValue(QOMPropertyTypeString, self.name, "")


class RQInstance(object):
    "Descriptor for QOM object at runtime."

    def __init__(self, obj, _type):
        """
    :type obj: debug.Value
    :param obj:
        is runtime variable representing that instance

    :type type: RQOMType
    :param type:
        is descriptor for QOM type of that instance
        """
        self.obj = obj
        self.type = _type
        self.related = []


        # QOM type specific fields

        # object
        self.properties = {}

        # qemu:memory-region:
        # bus
        self.name = None

        # qemu:memory-region
        self.size = None

        # device: the bus this device is attached to
        # bus: the device controlling this bus
        self.parent = None

        # device: buses controlled by the device
        # bus: devices on the bus
        self.children = []

        # irq:
        # tuple (dev. `RQInstance`, GPIO name, GPIO index)
        #     for split IRQ: `dst[0]` is `self`
        self.src = None
        self.dst = None

    def relate(self, qinst):
        self.related.append(qinst)
        qinst.related.append(self)

    def unrelate(self, qinst):
        self.related.remove(qinst)
        qinst.related.renove(self)

    def account_property(self, prop):
        """ Helper for property accounting.

    :type prop: Value
    :param prop:
        represents corresponding variable of type `ObjectProperty`
        """
        if prop.type.code == TYPE_CODE_PTR:
            prop = prop.dereference()
        if not prop.is_global:
            prop = prop.to_global()

        rqo_prop = RQObjectProperty(self, prop)
        self.properties[rqo_prop.name] = rqo_prop

        return rqo_prop


@notifier(
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
        verbose = False,
        **kw
    ):
        """
    :type qom_tree: RQOMTree

    :param interrupt:
        Interrupt QEmu process after machine is fully created.

        """
        super(MachineWatcher, self).__init__(dic,
            verbose = verbose,
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
        return i

    # Breakpoint handlers

    def on_obj_init_start(self):
        # object_initialize_with_type, before `object_init_with_type`

        # v2.12.0
        """object.c:384 4743c23509a51bd4ee85cc272287a41917d1be35
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

        # v2.12.0
        """object.c:386 4743c23509a51bd4ee85cc272287a41917d1be35
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
        # machine_run_board_init

        # v2.12.0
        """hw/core/machine.c:829 4743c23509a51bd4ee85cc272287a41917d1be35
vl.c:4510 43ac51e66b421216856c752f9382cb6de3cfccad
"""

        rt = self.rt

        machine_obj = rt["machine"]
        self.machine = inst = self.account_instance(machine_obj)

        desc = inst.type.impl["class"].cast("MachineClass*")["desc"]

        if not self.verbose:
            return

        print("Machine creation started\nDescription: " +
            desc.fetch_c_string()
        )

    def on_mem_init_end(self):
        # return from memory_region_init

        # v2.12.0
        """memory.c:1153 4743c23509a51bd4ee85cc272287a41917d1be35
memory.c:1009 0ab8ed18a6fe98bfc82705b0f041fbf2a8ca5b60
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

        # v2.12.0
        """hw/core/machine.c:830 4743c23509a51bd4ee85cc272287a41917d1be35
vl.c:4511 43ac51e66b421216856c752f9382cb6de3cfccad
"""

        self.remove_breakpoints()
        if self.interrupt:
            self.rt.target.interrupt()

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

        # v2.12.0
        """object.c:975 4743c23509a51bd4ee85cc272287a41917d1be35
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
            prop.obj.obj.address,
            prop.obj.type.name,
            prop.name,
            prop.type
        ))

    def on_obj_prop_set(self):
        # object_property_set (prop. exists and has a setter)

        # v2.12.0
        """object.c:1122 4743c23509a51bd4ee85cc272287a41917d1be35
object.c:1094 63f7b10bc552be8a2cd1da87e8b27f9a5a217b91
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
            prop.obj.obj.address,
            prop.obj.type.name,
            prop.name,
            prop.type,
            rt["v"].fetch_pointer()
        ))

    def on_qbus_realize(self):
        # qbus_realize, parent may be NULL

        # v2.12.0
        "hw/core/bus.c:101 4743c23509a51bd4ee85cc272287a41917d1be35"

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

        # v2.12.0
        "hw/core/bus.c:123 4743c23509a51bd4ee85cc272287a41917d1be35"

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
        # bus_add_child

        # v2.12.0
        """hw/core/qdev.c:73 4743c23509a51bd4ee85cc272287a41917d1be35
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
        """hw/core/qdev.c:57 4743c23509a51bd4ee85cc272287a41917d1be35
 hw/core/qdev.c:70 67980031d234aa90524b83bb80bb5d1601d29076
 """

        print("not implemented")

    def on_qdev_get_gpio_in_named(self):
        # qdev_get_gpio_in_named, return

        # v2.12.0
        """core/qdev.c:456 4743c23509a51bd4ee85cc272287a41917d1be35
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

        # v2.12.0
        """core/qdev.c:479 4743c23509a51bd4ee85cc272287a41917d1be35
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

        # v2.12.0
        """core/irq.c:122 4743c23509a51bd4ee85cc272287a41917d1be35
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
        # v2.12.0
        "pc_piix.c:301 4743c23509a51bd4ee85cc272287a41917d1be35"

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
        # v.2.12.0
        "piix4.c:578 4743c23509a51bd4ee85cc272287a41917d1be35"

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

    def __init__(self, watcher, machine, tracker):
        """
    :type watcher: MachineWatcher
    :type machine: MachineNode
    :type tracker: GUIProjectHistoryTracker
        """
        self.watcher = watcher
        self.machine = machine
        self.tracker = tracker
        self.proxy = tracker.get_machine_proxy(machine)

        # auto assign event handlers
        for name, ref in getmembers(type(self)):
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
        cc = CastCatcher(inst)

        ii = _type.instance_init
        if ii:
            for addr in ii.epilogues:
                target.add_br(target.get_hex_str(addr), cc)

        realize = _type.realize
        if realize:
            for addr in realize.epilogues:
                target.add_br(target.get_hex_str(addr), cc)

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


re_qemu_system_x = compile(".*qemu-system-.+$")


class QArgumentParser(ArgumentParser):

    def error(self, *args, **kw):
        stderr.write("Error in argument string. Ensure that `--` is passed"
            " before QEMU and its arguments.\n"
        )
        super(QArgumentParser, self).error(*args, **kw)


class QEmuWatcherGUI(GUITk):
    "Showing runtime state of machine."

    def __init__(self, pht, mach_desc, runtime):
        GUITk.__init__(self, wait_msec = 1)

        self.title(_("QEmu Watcher"))

        self.pht = pht
        self.rt = runtime

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)

        mdsw = MachineDescriptionSettingsWidget(mach_desc, self)
        mdsw.grid(row = 0, column = 0, sticky = "NESW")
        mdsw.mw.mdw.var_physical_layout.set(False)
        self.mdsw = mdsw

        # magic with layouts
        pht.p.add_layout(mach_desc.name, mdsw.gen_layout()).widget = mdsw

        self.task_manager.enqueue(self.co_rsp_poller())

        self.hk = hk = HotKey(self)
        hk.add_bindings([
            HotKeyBinding(self._on_save,
                key_code = 39,
                description = _("Save machine"),
                symbol = "S"
            )
        ])

        menubar = VarMenu(self)
        self.config(menu = menubar)

        filemenu = VarMenu(menubar, tearoff = False)
        menubar.add_cascade(label = _("File"), menu = filemenu)

        filemenu.add_command(
            label = _("Save machine"),
            command = self._on_save,
            accelerator = hk.get_keycode_string(self._on_save)
        )

    def _on_save(self):
        fname = asksaveas(self,
            [(_("QDC GUI Project defining script"), ".py")],
            title = _("Save machine")
        )

        if not fname:
            return

        self.save_project_to_file(fname)

    def try_save_project_to_file(self, file_name):
        try:
            open(file_name, "wb").close()
        except IOError as e:
            if not e.errno == 13: # Do not remove read-only files
                try:
                    remove(file_name)
                except:
                    pass

            showerror(
                title = _("Cannot save project").get(),
                message = str(e)
            )
            return

        self.save_project_to_file(file_name)

    def save_project_to_file(self, file_name):
        project = self.pht.p

        project.sync_layouts()

        # Ensure that all machine nodes are in corresponding lists
        for d in project.descriptions:
            if isinstance(d, MachineNode):
                d.link(handle_system_bus = False)

        pythonize(project, file_name)

    def co_rsp_poller(self):
        rt = self.rt
        target = rt.target

        target.run_no_block()

        target.finished = False
        target._interrupt = False
        while not target._interrupt:
            yield
            try:
                target.poll()
            except:
                print_exc()
                print("Target PC 0x%x" % (rt.get_reg(rt.pc)))
                break

        yield

        if not target.finished:
            target.finished = True
            target.rsp.finish()


def main():
    ap = QArgumentParser(
        description = "QEMU runtime introspection tool"
    )
    ap.add_argument("qarg",
        nargs = "+",
        help = "QEMU executable and arguments to it. Prefix them with `--`."
    )
    ap.add_argument("-q",
        dest = "qsrc",
        help = "QEMU src directory."
    )
    args = ap.parse_args()

    # executable
    qemu_cmd_args = args.qarg

    # src directory
    qemu_src_dir = args.qsrc

    # debug info
    qemu_debug = qemu_cmd_args[0]

    elf = InMemoryELFFile(qemu_debug)
    if not elf.has_dwarf_info():
        stderr("%s does not have DWARF info. Provide a debug QEMU build\n" % (
            qemu_debug
        ))
        return -1

    di = elf.get_dwarf_info()

    if di.pubtypes is None:
        print("%s does not contain .debug_pubtypes section. Provide"
            " -gpubnames flag to the compiler" % qemu_debug
        )

    dic = DWARFInfoCache(di,
        symtab = elf.get_section_by_name(b".symtab")
    )

    gvl_adptr = GitLineVersionAdapter(qemu_src_dir)

    qomtr = QOMTreeReverser(dic,
        interrupt = False,
        verbose = True,
        line_adapter = gvl_adptr
    )

    if "-i386" in qemu_debug or "-x86_64" in qemu_debug:
        MWClass = PCMachineWatcher
    else:
        MWClass = MachineWatcher

    mw = MWClass(dic, qomtr.tree,
        interrupt = True,
        line_adapter = gvl_adptr
    )

    mach_desc = MachineNode("runtime-machine", "")
    proj = GUIProject(
        descriptions = [mach_desc]
    )
    pht = GUIProjectHistoryTracker(proj, proj.history)

    MachineReverser(mw, mach_desc, pht)

    # auto select free port for gdb-server
    for port in range(4321, 1 << 16):
        test_socket = socket(AF_INET, SOCK_STREAM)
        try:
            test_socket.bind(("", port))
        except:
            pass
        else:
            break
        finally:
            test_socket.close()

    qemu_debug_addr = "localhost:%u" % port

    qemu_proc = Process(
        target = system,
        # XXX: if there are spaces in arguments this code will not work.
        args = (" ".join(["gdbserver", qemu_debug_addr] + qemu_cmd_args),)
    )

    qemu_proc.start()

    qemu_debugger = AMD64(qemu_debug_addr,
        host = True
    )

    rt = Runtime(qemu_debugger, dic)

    qomtr.init_runtime(rt)
    mw.init_runtime(rt)

    tk = QEmuWatcherGUI(pht, mach_desc, rt)

    tk.geometry("1024x1024")
    tk.mainloop()

    if not qemu_debugger.finished:
        qemu_debugger.rsp.finish()

    qomtr.to_file("qom-by-q.i.dot")

    qemu_proc.join()

    gvl_adptr.cm.store_cache()


if __name__ == "__main__":
    exit(main())
