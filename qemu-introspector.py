from qemu import (
    QOMPropertyTypeLink,
    QOMPropertyTypeString,
    QOMPropertyTypeBoolean,
    QOMPropertyTypeInteger,
    QOMPropertyValue,
    MOp_AddDevProp,
    MOp_SetDevProp,
    MOp_SetDevParentBus,
    MachineNode,
    q_event_dict,
    q_event_list
)
from argparse import (
    ArgumentTypeError,
    ArgumentParser,
    ArgumentError
)
from re import (
    compile
)
from collections import (
    defaultdict,
    deque
)
from multiprocessing import (
    Process
)
from os import (
    system
)
from os.path import (
    isfile,
    split,
    join
)
from sys import (
    stderr,
    path as python_path
)
# Add ours pyelftools to PYTHON_PATH before importing of pyrsp to substitute
# system pyelftools imported by pyrsp
for mod in ("pyrsp", "pyelftools"):
    path = join(split(__file__)[0], mod)
    if path not in python_path:
        python_path.insert(0, path)

from pyrsp.targets import (
    AMD64
)
from pyrsp.elf import (
    InMemoryELFFile,
    DWARFInfoAccelerator,
    ELF,
    AddrDesc
)
from elftools.common.intervalmap import (
    intervalmap
)
from hashlib import (
    sha1
)
from common import (
    mlget as _,
    notifier,
    sort_topologically,
    PyGenerator,
    execfile
)
from traceback import (
    print_exc
)
from pyrsp.utils import (
    lazy,
    switch_endian,
    decode_data
)
from pyrsp.gdb import (
    Value,
    Type
)
from pyrsp.type import (
    TYPE_CODE_PTR
)
from pyrsp.runtime import (
    Runtime
)
from itertools import (
    count
)
from inspect import (
    getmembers,
    ismethod
)
from graphviz import (
    Digraph
)
from widgets import (
    GUIProjectHistoryTracker,
    GUIProject,
    MachineDescriptionSettingsWidget,
    GUITk
)
from gdb import (
    Watcher
)


def checksum(stream, block_size):
    "Given a stream computes SHA1 hash by reading block_size per block."

    buf = stream.read(block_size)
    hasher = sha1()
    while len(buf) > 0:
        hasher.update(buf)
        buf = stream.read(block_size)


def elf_stream_checksum(stream, block_size = 65536):
    return checksum(stream, block_size)


def elf_checksum(file_name):
    with open(file_name, "rb") as s: # Stream
        return elf_stream_checksum(s)


class QELFCache(ELF):
    """
Extended version of ELF file cache.

Extra features:
- SHA1 based modification detection code, `mdc` field.
- serialization to Python script by `PyGeneratior`

    """

    # names of fields to serialize
    SAVED = (
        # QELFCache fields
        "mdc",
        # backing class fields
        "entry", "rel", "workarea", "symbols", "addresses", "file_map",
        "src_map", "addr_map", "routines", "vars",
    )

    def __init__(self, name, **kw):
        mdc = kw.get("mdc", None)
        file_mdc = elf_checksum(name)

        if mdc is None:
            # build the cache
            super(QELFCache, self).__init__(name)
            self.mdc = file_mdc
        else:
            # check the cache
            if file_mdc != mdc:
                raise ValueError("File SHA1 %r was changed. Expected: %r" % (
                    file_mdc, mdc
                ))

            absent = deque()

            for field in self.SAVED:
                try:
                    val = kw[field]
                except KeyError:
                    absent.append(val)
                setattr(self, field, val)

            if absent:
                raise TypeError("Some data are absent: " + ", ".join(absent))

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field("")
        gen.pprint(self.name)
        for field in self.SAVED:
            gen.gen_field(field + " = ")
            gen.pprint(getattr(self, field))
        gen.gen_end()

    def __dfs_children__(self):
        return [self.addr_map] + list(self.file_map.values())

    def __var_base__(self):
        return "qec"


re_qemu_system_x = compile(".*qemu-system-.+$")


class QArgumentParser(ArgumentParser):

    def error(self, *args, **kw):
        stderr.write("Error in argument string. Ensure that `--` is passed"
            " before QEMU and its arguments.\n"
        )
        super(QArgumentParser, self).error(*args, **kw)


class RQOMTree(object):
    """ QEmu object model tree descriptor at runtime
    """

    def __init__(self):
        self.name2type = {}
        self.addr2type = {}

        # Types are found randomly (i.e. not in parent-first order).
        self.unknown_parents = defaultdict(list)

    def account(self, impl, name = None, parent = None):
        "Add a type"
        if impl.type.code == TYPE_CODE_PTR:
            # Pointer `impl` is definetly a value on the stack. It cannot be
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
    """ QEmu object model type descriptor at runtime
    """

    def __init__(self, tree, impl, name = None, parent = None):
        """
        :param impl:
            global runtime `Value` which is pointer to the `TypeImpl`

        :param name:
            `str`ing read form impl

        :param parent:
            `str`ing too
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
        self._instance_casts = set()

        # "device"
        self.realize = None

    def instance_casts(self):
        """ A QOM instance can be casted to C types corresponding to its
        ancestors too.
        """
        ret = set(self._instance_casts)
        for a in self.iter_ancestors():
            for cast in a._instance_casts:
                ret.add(cast)
        return ret

    # TODO: there is too many boilerplate code for `TypeImpl` fields access.
    # Consider to rewrite it in a common way. `__getitem__` ?

    @lazy
    def instance_init(self):
        impl = self.impl

        addr = impl["instance_init"].fetch_pointer()
        if addr:
            return impl.dia.subprogram(addr)
        return None

    @lazy
    def class_init(self):
        impl = self.impl

        addr = impl["class_init"].fetch_pointer()
        if addr:
            return impl.dia.subprogram(addr)
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
        t = self.tree.name2type[name]

        for a in self.iter_ancestors():
            if a is t:
                return True
        return False


# Characters disalowed in node ID according to DOT language. That is not a full
# list though.
# https://www.graphviz.org/doc/info/lang.html
re_DOT_ID_disalowed = compile(r"[^a-zA-Z0-9_]")


def gv_node(label):
    return re_DOT_ID_disalowed.sub("_", label)


class QOMTreeGetter(Watcher):

    def __init__(self, dia, interrupt = True, verbose = False):
        """
        :param interrupt:
            Stop QEmu and exit `RemoteTarget.run`.
        """
        super(QOMTreeGetter, self).__init__(dia, verbose = verbose)

        self.tree = RQOMTree()
        self.interrupt = interrupt

    def on_type_register_internal(self):
        "object.c:139" # type_register_internal

        t = self.tree.account(self.rt["ti"])

        if self.verbose:
            print("%s -> %s" % (t.parent, t.name))

    def on_type_initialize(self):
        "object.c:344" # now the type and its ancestors are initialized

        rt = self.rt
        type_impl = rt["ti"]

        ti_addr = type_impl.fetch_pointer()
        a2t = self.tree.addr2type

        if ti_addr not in a2t:
            # There are interfaces providing variations of regular types. They
            # do not path throug type_register_internal because its TypeInfo is
            # created and used directly by type_initialize_interface.
            return

        t = a2t[ti_addr]

        if t.implements("device"):
            cls = type_impl["class"]

            dev_cls = cls.cast("DeviceClass *")
            realize_addr = dev_cls["realize"].fetch_pointer()

            if realize_addr:
                t.realize = rt.dia.subprogram(realize_addr)

    def on_main(self):
        "vl.c:3075" # main, just after QOM module initialization

        if self.interrupt:
            self.rt.target.interrupt()

    def to_file(self, dot_file_name):
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
            if t._instance_casts:
                label += "\\n*"
                for cast in t._instance_casts:
                    label += "\\n" + cast.name

            graph.node(n, label = label)
            if t.parent:
                graph.edge(gv_node(t.parent), n)

        with open(dot_file_name, "wb") as f:
            f.write(graph.source)


class RQObjectProperty(object):
    """ Runtime QOM object property
    """

    def __init__(self, obj, prop, name = None, type = None):
        """
        :param obj:
            is corresponding `QInstance`
        :param prop:
            is `Value` representing `ObjectProperty`
        """
        self.obj = obj
        self.prop = prop
        if name is None:
            name = prop["name"].fetch_c_string()
        if type is None:
            type = prop["type"].fetch_c_string()
        self.name = name
        self.type = type

    @lazy
    def as_qom(self):
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


class QInstance(object):
    """ Descriptor for QOM object at runtime.
    """

    def __init__(self, obj, type):
        """
        :param obj:
            Global runtime `Value`.

        :param type:
            instance of `RQOMType`
        """
        self.obj = obj
        self.type = type
        self.related = []

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

    def relate(self, qinst):
        self.related.append(qinst)
        qinst.related.append(self)

    def unrelate(self, qinst):
        self.related.remove(qinst)
        qinst.related.renove(self)

    def account_property(self, prop):
        """
        :param prop:
            is `Value` representing `ObjectProperty`
        """
        if prop.type.code == TYPE_CODE_PTR:
            prop = prop.dereference()
        if not prop.is_global:
            prop = prop.to_global()

        rqo_prop = RQObjectProperty(self, prop)
        self.properties[rqo_prop.name] = rqo_prop

        return rqo_prop


@notifier(
    "device_creating", # QInstance
    "device_created", # QInstance
    "bus_created", # QInstance
    "bus_attached", # QInstance bus, QInstance device
    "device_attached", # QInstance device, QInstance bus
    "property_added", # QInstance, RQObjectProperty
    "property_set", # QInstance, RQObjectProperty, Value
)
class MachineWatcher(Watcher):
    """ Watches for QOM API calls to reconstruct machine model and monitor its
    state at runtime.
    """

    def __init__(self, dia, qom_tree, verbose = False):
        super(MachineWatcher, self).__init__(dia, verbose = verbose)
        self.tree = qom_tree
        # addr -> QInstance mapping
        self.instances = {}
        self.machine = None

    def account_instance(self, obj, type_impl = None):
        """
        :param obj:
            `Value` representing object structure
        """
        if obj.type.code == TYPE_CODE_PTR:
            obj = obj.dereference()
        if not obj.is_global:
            obj = obj.to_global()

        if type_impl is None:
            type_impl = obj.cast("Object")["class"]["type"]

        addr = type_impl.fetch_pointer()
        rqom_type = self.tree.addr2type[addr]

        i = QInstance(obj, rqom_type)
        self.instances[obj.address] = i
        return i

    # Breakpoint handlers

    def on_obj_init_start(self):
        "object.c:384" # object_initialize_with_type

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
            # print("Creating memory")
            self.current_memory = inst

    def on_obj_init_end(self):
        "object.c:386" # object_initialize_with_type

        if self.machine is None:
            return

        rt = self.rt
        addr = rt["obj"].fetch_pointer()

        inst = self.instances[addr]

        if inst.type.implements("device"):
            self.__notify_device_created(inst)

    def on_board_init_start(self):
        "hw/core/machine.c:829" # machine_run_board_init

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
        "memory.c:1153" # return from memory_region_init

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
        "hw/core/machine.c:830" # machine_run_board_init

        self.remove_breakpoints()
        self.rt.target.interrupt()

        if not self.verbose:
            return

        print("Machine creation ended: " +
            # explicit casting is not required here, it's just for testing
            self.machine.type.impl.cast("TypeImpl")["name"].fetch_c_string()
        )

    def on_obj_prop_add(self):
        "object.c:976" # return from object_property_add

        if self.machine is None:
            return

        rt = self.rt
        obj_addr = rt["obj"].fetch_pointer()

        try:
            inst = self.instances[obj_addr]
        except KeyError:
            print("Skipping property for unaccounted object 0x%x" % obj_addr)
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
        "object.c:1122" # object_property_set (prop. exists and has a setter)

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
        "hw/core/bus.c:101" # qbus_realize, parrent may be NULL
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
        "hw/core/bus.c:123" # bus_unparent, before actual unparanting
        # TODO: test me
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
        "hw/core/qdev.c:73" # bus_add_child
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
        "hw/core/qdev.c:57" # bus_remove_child, before actual unparanting
        print("not implemented")


class CastCatcher(object):
    """ A breakpoint handler that inspects all subprogram pointers those do
    refer to a given QOM instance and remebers types of those pointers as
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
            qom_type._instance_casts.add(datum_type.target_type)


class MachineReverser(object):

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
                target.set_br(target.get_hex_str(addr), cc)

        realize = _type.realize
        if realize:
            for addr in realize.epilogues:
                target.set_br(target.get_hex_str(addr), cc)

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
            qom_prop.prop_val, # XXX: recover from `val`
            qom_prop,
            inst2id[obj]
        )
        self.proxy.commit()

def main():
    ap = QArgumentParser(
        description = "QEMU runtime introspection tool"
    )
    ap.add_argument("qarg",
        nargs = "+",
        help = "QEMU executable and arguments to it. Prefix them with `--`."
    )
    args = ap.parse_args()

    # executable
    qemu_cmd_args = args.qarg

    # debug info
    qemu_debug = qemu_cmd_args[0]

    loaded = {
        "AddrDesc": AddrDesc,
        "QELFCache": QELFCache,
        "intervalmap" : intervalmap
    }

    elf = InMemoryELFFile(qemu_debug)
    if not elf.has_dwarf_info():
        stderr("%s does not have DWARF info. Provide a debug QEMU build\n" % (
            qemu_debug
        ))
        return -1

    di = elf.get_dwarf_info()

    if di.pubtypes is None:
        print("%s does not contain .debug_pubtypes section. Provide"
            " -gpubnames flag to the compiller" % qemu_debug
        )

    dia = DWARFInfoAccelerator(di,
        symtab = elf.get_section_by_name(b".symtab")
    )

    qomtg = QOMTreeGetter(dia,
        # verbose = True,
        interrupt = False
    )
    mw = MachineWatcher(dia, qomtg.tree,
        # verbose = True
    )

    mach_desc = MachineNode("runtime-machine", "")
    proj = GUIProject(
        descriptions = [mach_desc]
    )
    pht = GUIProjectHistoryTracker(proj, proj.history)

    MachineReverser(mw, mach_desc, pht)

    qemu_debug_addr = "localhost:4321"

    qemu_proc = Process(
        target = system,
        # XXX: if there are spaces in arguments this code will not work.
        args = (" ".join(["gdbserver", qemu_debug_addr] + qemu_cmd_args),)
    )

    qemu_proc.start()

    qemu_debugger = AMD64(qemu_debug_addr,
        # verbose = True,
        host = True
    )

    rt = Runtime(qemu_debugger, dia)

    mw.init_runtime(rt)
    qomtg.init_runtime(rt)

    qemu_debugger.finished = False

    def co_rsp_poller(rsp = qemu_debugger):
        rsp.run_no_block()

        rsp._interrupt = False
        while not rsp._interrupt:
            yield
            try:
                rsp.poll()
            except:
                print_exc()
                print("Target PC 0x%x" % (rt.get_reg(rt.pc)))

                if not qemu_debugger.finished:
                    qemu_debugger.finished = True
                    qemu_debugger.rsp.finish()

                break

        yield

        if not qemu_debugger.finished:
            qemu_debugger.finished = True
            qemu_debugger.rsp.finish()

    tk = GUITk(wait_msec = 1)
    tk.title(_("QEmu Watcher"))

    tk.pht = pht

    tk.task_manager.enqueue(co_rsp_poller())

    tk.grid()
    tk.rowconfigure(0, weight = 1)
    tk.columnconfigure(0, weight = 1)

    mdsw = MachineDescriptionSettingsWidget(mach_desc, tk)
    mdsw.grid(row = 0, column = 0, sticky = "NESW")

    tk.geometry("1024x1024")
    tk.mainloop()

    if not qemu_debugger.finished:
        qemu_debugger.rsp.finish()

    # XXX: on_finish method is not called by RemoteTarget
    qomtg.to_file("qom-by-q.i.dot")

    qemu_proc.join()


def runtime_based_var_getting(rt):
    target = rt.target

    def type_reg(resumes = [1]):
        print("type reg")
        info = rt["info"]
        name = info["name"]
        parent = info["parent"]

        p_name = parent.fetch(target.address_size)
        print("parent name at 0x%0*x" % (target.tetradsize, p_name))

        print("%s -> %s" % (parent.fetch_c_string(), name.fetch_c_string()))

        rt.on_resume()

        if resumes[0] == 0:
            rt.target.interrupt()
        else:
            resumes[0] -= 1

    return type_reg


def explicit_var_getting(rt, object_c):
    dia = rt.dia
    target = rt.target
    # get info argument of type_register_internal function
    dia.account_subprograms(object_c)
    type_register_internal = dia.subprograms["type_register_internal"][0]
    info = type_register_internal.data["info"]

    print("info loc: %s" % info.location)

    def type_reg_fields():
        print("type reg")
        info_loc = info.location.eval(rt)
        info_loc_str = "%0*x" % (target.tetradsize, info_loc)
        print("info at 0x%s" % info_loc_str)
        info_val = switch_endian(
            decode_data(
                target.get_mem(info_loc_str, 8)
            )
        )
        print("info = 0x%s" % info_val)
        pt = Type(dia, info.type_DIE)
        t = pt.target()
        print("info type: %s %s" % (" ".join(t.modifiers), t.name))
        # t is `typedef`, get the structure
        st = t.target()

        for f in st.fields():
            print("%s %s; // %s" % (f.type.name, f.name, f.location))

    def type_reg_name():
        v = Value(info, rt)
        name = v["name"]
        parent = v["parent"]

        p_name = parent.fetch(target.address_size)
        print("parent name at 0x%0*x" % (target.tetradsize, p_name))

        print("%s -> %s" % (parent.fetch_c_string(), name.fetch_c_string()))

    def type_reg():
        type_reg_name()
        type_reg_fields()

        rt.on_resume()

    return type_reg


def test_call_frame(type_register_internal, br_addr):
    frame = type_register_internal.frame_base

    print("frame base: %s" % frame)

    fde = dia.fde(br_addr)
    print("fde = %s" % fde)

    table_desc = fde.get_decoded()
    table = table_desc.table

    for row in table:
        print(row)

    call_frame_row = dia.cfr(br_addr)
    print("call frame: %s" % call_frame_row)
    cfa = dia.cfa(br_addr)
    print("CFA: %s" % cfa)


def test_subprograms(dia):
    cpu_exec = dia.get_CU_by_name("cpu-exec.c")

    # For testing:
    # pthread_atfork.c has subprogram data referencing location lists
    # ioport.c contains inlined subprogram, without ranges

    for cu in [cpu_exec]: # dia.iter_CUs():
        print(cu.get_top_DIE().attributes["DW_AT_name"].value)
        sps = dia.account_subprograms(cu)
        for sp in sps:
            print("%s(%s) -> %r" % (
                sp.name,
                ", ".join(varname for (varname, var) in sp.data.items()
                          if var.is_argument
                ),
                sp.ranges
            ))

            for varname, var in sp.data.items():
                print("    %s = %s" % (varname, var.location))


def test_line_program_sizes(dia):
    for cu in dia.iter_CUs():
        name = cu.get_top_DIE().attributes["DW_AT_name"].value
        print("Getting line program for %s" % name)
        li = dia.di.line_program_for_CU(cu)
        entries = li.get_entries()
        print("Prog size: %u" % len(entries))


def test_line_program(dia):
    cpu_exec = dia.get_CU_by_name("cpu-exec.c")

    lp = dia.di.line_program_for_CU(cpu_exec)
    entrs = lp.get_entries()

    print("%s line program (%u)" % (
        cpu_exec.get_top_DIE().attributes["DW_AT_name"].value,
        len(entrs)
    ))
    # print("\n".join(repr(e.state) for e in entrs))

    dia.account_line_program(lp)
    lmap = dia.find_line_map("cpu-exec.c")

    for (l, r), entries in lmap.items():
        s = entries[0].state
        print("[%6i;%6i]: %s 0x%x" % (
            1 if l is None else l,
            r - 1,
            "S" if s.is_stmt else " ",
            s.address
        ))


def test_CU_lookup(dia):
    dia.get_CU_by_name("tcg.c")
    print("found tcg.c")
    dia.get_CU_by_name(join("ui", "console.c"))
    print("found ui/vl.c")
    dia.get_CU_by_name(join("ui", "console.c"))
    print("found ui/vl.c again")
    dia.get_CU_by_name("console.c")
    print("found console.c")
    try:
        dia.get_CU_by_name("virtio-blk.c")
    except:
        dia.get_CU_by_name(join("block", "virtio-blk.c"))
        print("found block/virtio-blk.c")
    else:
        print("short suffix exception is expected")
    try:
        dia.get_CU_by_name("apic.c")
    except:
        dia.get_CU_by_name(join("kvm", "apic.c"))
        print("found kvm/apic.c")
    else:
        print("short suffix exception is expected")


def test_cache(qemu_debug):
    cache_file = qemu_debug + ".qec"

    if isfile(cache_file):
        print("Trying to load cache from %s" % cache_file)
        try:
            execfile(cache_file, globals = loaded)
        except:
            stderr.write("Cache file execution error:\n")
            print_exc()

        cache = loaded.get("qec", None)

        print("Cache was %sloaded." % ("NOT " if cache is None else ""))
    else:
        cache = None

    if cache is None:
        print("Building cache of %s" % qemu_debug)
        cache = QELFCache(qemu_debug)

        print("Saving cache to %s" % cache_file)
        with open(cache_file, "wb") as f:
            PyGenerator().serialize(f, cache)


if __name__ == "__main__":
    exit(main())
