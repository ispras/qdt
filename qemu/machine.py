__all__ = [
    "MachineType"
  , "UnknownMachineNodeType"
  , "UnknownBusBridgeType"
  , "IncorrectPropertyValue"
  , "UnknownPropertyType"
  , "UnknownMemoryNodeType"
]

from .qom_common import (
    QOMPropertyTypeLink,
    QOMPropertyTypeString,
    QOMPropertyTypeBoolean,
    QOMPropertyTypeInteger
)
from .qom import (
    QOMType
)
from source import (
    BodyTree,
    Declare,
    OpDeclareAssign,
    MCall,
    NewLine,
    Call,
    Pointer,
    Macro,
    Source,
    Type,
    TypeNotRegistered,
    Function
)
from .machine_nodes import (
    CPUNode,
    SystemBusDeviceNode,
    BusNode,
    SystemBusNode,
    PCIExpressBusNode,
    IRQHub,
    MemoryNode,
    MemorySASNode,
    MemoryAliasNode,
    MemoryRAMNode,
    MemoryROMNode,
    DeviceNode,
    IRQLine,
    PCIExpressDeviceNode
)
from common import (
    cached,
    reset_cache,
    mlget as _,
    sort_topologically
)
from os.path import (
    join as join_path
)
from .version import (
    get_vp
)
from six import (
    integer_types
)
from collections import (
    OrderedDict
)

class UnknownMachineNodeType(ValueError):
    pass

class UnknownBusBridgeType(ValueError):
    def __init__(self, primary_bus, secondary_bus):
        super(UnknownBusBridgeType, self).__init__(
            "%s <-> %s" % (str(type(primary_bus)), str(type(secondary_bus)))
        )

class IncorrectPropertyValue(ValueError):
    pass

class UnknownPropertyType(ValueError):
    pass

class UnknownMemoryNodeType(ValueError):
    pass

class IRQHubLayout(object):
    def __init__(self, hub, generator):
        leafs = [ irq for irq in hub.irqs if irq.src[0] == hub ]
        while len(leafs) > 1:
            new_leafs = []
            while leafs:
                left = leafs.pop()
                if not leafs:
                    new_leafs.append(left)
                else:
                    right = leafs.pop()
                    new_leafs.append((left, right))
            leafs = new_leafs
        self.root = leafs[0]

        self.gen = generator
        self.hub = hub

    def _gen_irq_get(self, parent_name, node, inner_base):
        if isinstance(node, IRQLine):
            # leaf
            dst = node.dst
            if isinstance(dst[0], IRQHub):
                """ Declaration and definition of destination hub must be
                already generated. A hub (its root) is an IRQ line. So, use
                initialize self IRQ with IRQ of the destination hub. """
                def_code = "    {parent_name}@b=@s{child_name};\n".format(
                    parent_name = parent_name,
                    child_name = self.gen.node_map[dst[0]],
                )
                return ("", def_code)
            else:
                return ("", self.gen.gen_irq_get(dst, parent_name))
        else:
            # inner node
            self.gen.use_type_name("qemu_irq_split")

            decl_code = ""
            def_code = ""
            children_names = []

            for child, side in zip(node, ["_l", "_r"]):
                if isinstance(child, IRQLine):
                    child_name = self.gen.node_map[child]
                else:
                    child_name = self.gen.provide_name_for_node(child,
                        inner_base + side
                    )
                children_names.append(child_name)

                child_code = self._gen_irq_get(child_name, child,
                    inner_base + side
                )

                decl_code += child_code[0] + "    qemu_irq %s;\n" % child_name
                def_code += child_code[1]

            def_code += """\
    {parent_name} = qemu_irq_split(@a{children});
""".format(
    parent_name = parent_name,
    children = ",@s".join(children_names)
            )
            return (decl_code, def_code)

    def gen_irq_get(self):
        root_name = self.gen.node_map[self.hub]
        return self._gen_irq_get(root_name, self.root, root_name)

class MachineType(QOMType):

    def __init__(self, name, directory,
            cpus = [],
            devices = [],
            buses = [],
            irqs = [],
            mems = [],
            irq_hubs = []
        ):
        super(MachineType, self).__init__(name, directory)

        self.__lazy__ = []

        self.desc = "TODO: provide description for " + name

        self.cpus = cpus
        self.devices = devices
        self.buses = buses
        self.irqs = irqs
        self.mems = mems
        self.irq_hubs = irq_hubs

    def reset_generator(self):
        self.node_map = {}
        self.init_used_types = []
        self.hub_layouts = {}
        self.provide_node_names()

        reset_cache(self)

    def use_type(self, t):
        if t in self.init_used_types:
            return
        self.init_used_types.append(t)

    def use_type_name(self, name):
        t = Type[name]
        self.use_type(t)

    def provide_name_for_node(self, node, base):
        """ Returns name of variable for given node. Does generate and remember
        a new name if required. """
        try:
            return self.node_map[node]
        except KeyError:
            if base in self.node_map:
                name = base + "_%u" % node.id
            else:
                # do not use suffix with id for first node with such base
                name = base

            self.node_map[name] = node
            self.node_map[node] = name

            return name

    def provide_node_names(self):
        for nodes in [
            self.cpus,
            self.devices,
            self.buses,
            self.irqs,
            self.irq_hubs,
            self.mems
        ]:
            for n in nodes:
                self.provide_name_for_node(n, n.var_base)

    def gen_prop_val(self, prop):
        if isinstance(prop.prop_val, str) and Type.exists(prop.prop_val):
            self.use_type_name(prop.prop_val)
            return prop.prop_val
        if prop.prop_type == QOMPropertyTypeString:
            return "\"%s\"" % str(prop.prop_val)
        elif prop.prop_type == QOMPropertyTypeBoolean:
            if not isinstance(prop.prop_val, (bool,) + integer_types):
                raise IncorrectPropertyValue("%s is %s, expected bool" % (
                    prop.prop_name, type(prop.prop_val).__name__
                ))

            self.use_type_name("bool")
            return "true" if prop.prop_val else "false"
        elif prop.prop_type == QOMPropertyTypeInteger:
            if not isinstance(prop.prop_val, integer_types):
                raise IncorrectPropertyValue()

            return "0x%x" % prop.prop_val
        elif prop.prop_type == QOMPropertyTypeLink:
            if prop.prop_val is None:
                self.use_type_name("NULL")

                return "NULL"
            else:
                self.use_type_name("OBJECT")

                return "OBJECT(%s)" % self.node_map[prop.prop_val]
        else:
            raise UnknownPropertyType()

    def gen_irq_get(self, irq, var_name):
        dst = irq[0]
        if isinstance(dst, IRQHub):
            raise RuntimeError("Cannot get an IRQ from a hub (%u)."
                " A hub _is_ an IRQ itself." % dst.id
            )

        self.use_type_name("DEVICE")

        if irq[2] is None:
            self.use_type_name("qdev_get_gpio_in")

            return """\
    {irq_name} = qdev_get_gpio_in(@aDEVICE({dst_name}),@s{dst_index});
""".format(
    irq_name = var_name,
    dst_name = self.node_map[dst],
    dst_index = irq[1],
            )
        else:
            gpio_name = irq[2]
            try:
                gpio_name_type = Type[gpio_name]
            except TypeNotRegistered:
                gpio_name = '"%s"' % gpio_name
            else:
                self.use_type(gpio_name_type)

            irq_get = Type["qdev_get_gpio_in_named"]
            self.use_type(irq_get)
            return """\
    {irq_name} = {irq_get}(@aDEVICE({dst_name}),@s{gpio_name},@s{dst_index});
""".format(
    irq_name = var_name,
    irq_get = irq_get.name,
    dst_name = self.node_map[dst],
    gpio_name = gpio_name,
    dst_index = irq[1],
            )

    def gen_irq_connect(self, irq, var_name):
        src = irq[0]
        if isinstance(src, IRQHub):
            raise RuntimeError("Cannot connect an IRQ to a hub (%u)."
                " A hub does use each its IRQ by itself." % src.id
            )

        if irq[2] is None:
            self.use_type_name("DEVICE")
            self.use_type_name("qdev_connect_gpio_out")

            return """\
    qdev_connect_gpio_out(@aDEVICE({src_name}),@s{src_index},@s{irq_name});
""".format(
    irq_name = var_name,
    src_name = self.node_map[src],
    src_index = irq[1]
            )
        else:
            sysbus_name = Type["SYSBUS_DEVICE_GPIO_IRQ"].text
            if sysbus_name == "\"%s\"" % irq[2] or "SYSBUS_DEVICE_GPIO_IRQ" == irq[2]:
                self.use_type_name("sysbus_connect_irq")
                self.use_type_name("SYS_BUS_DEVICE")

                return """\
    sysbus_connect_irq(@aSYS_BUS_DEVICE({src_name}),@s{src_index},@s{irq_name});
""".format(
    irq_name = var_name,
    src_name = self.node_map[src],
    src_index = irq[1]
                )
            else:
                self.use_type_name("DEVICE")
                self.use_type_name("qdev_connect_gpio_out_named")
                if Type.exists(irq[2]):
                    self.use_type_name(irq[2])

                return """\
    qdev_connect_gpio_out_named(@aDEVICE({src_name}),@s{gpio_name},@s{src_index},@s{irq_name});
""".format(
    irq_name = var_name,
    src_name = self.node_map[src],
    src_index = irq[1],
    gpio_name = irq[2] if Type.exists(irq[2]) else "\"%s\"" % irq[2]
                )

    def provide_hub_layout(self, hub):
        try:
            return self.hub_layouts[hub]
        except KeyError:
            hubl = IRQHubLayout(hub, self)
            self.hub_layouts[hub] = hubl
            return hubl

    def fill_source(self):
        glob_mem = get_vp("explicit global memory registration")

        if get_vp("property name before value"):
            prop_set_fmt = """
    {set_func}(@aOBJECT({dev_name}),@s{prop_name},@s{value},@sNULL);"""
        else:
            prop_set_fmt = """
    {set_func}(@aOBJECT({dev_name}),@s{value},@s{prop_name},@sNULL);"""

        all_nodes = sort_topologically(
            self.cpus +
            self.devices +
            self.buses +
            self.irqs +
            self.mems +
            self.irq_hubs
        )

        decl_code = ""
        def_code = ""
        self.reset_generator()

        skip_nl = False

        for idx, node in enumerate(all_nodes):
            if not skip_nl:
                if idx > 0:
                    def_code += "\n"
            else:
                skip_nl = False

            if isinstance(node, DeviceNode):
                if not get_vp("use qdev_new"):
                    # Since v5.0.0-rc0 it has been changed.
                    self.use_type_name("qdev_init_nofail")

                self.use_type_name("BUS")
                if Type.exists(node.qom_type):
                    self.use_type_name(node.qom_type)

                dev_name = self.node_map[node]

                props_code = ""
                for p in node.properties:
                    self.use_type_name("OBJECT")
                    self.use_type_name(p.prop_type.set_f)
                    if Type.exists(p.prop_name):
                        self.use_type_name(p.prop_name)
                    if isinstance(p.prop_val, str) and Type.exists(p.prop_val):
                        self.use_type_name(p.prop_val)

                    props_code += prop_set_fmt.format(
    set_func = p.prop_type.set_f,
    dev_name = dev_name,
    prop_name = p.prop_name if Type.exists(p.prop_name) else "\"%s\"" % p.prop_name,
    value = self.gen_prop_val(p)
                    )

                if isinstance(node, PCIExpressDeviceNode):
                    # TODO: support new approach. See:
                    #       pci: New pci_new(), pci_realize_and_unref() etc.
                    #       7411aa63a5f586329f87cbf318addaef427aa906
                    self.use_type_name("PCIDevice")
                    self.use_type_name("pci_create_multifunction")
                    self.use_type_name("bool")
                    self.use_type_name("DEVICE")

                    decl_code += "    PCIDevice *%s;\n" % dev_name
                    def_code += """\
    {dev_name} = pci_create_multifunction(@a{bus_name},@sPCI_DEVFN({slot},@s{func}),@s{multifunction},@s{qom_type});{props_code}
    qdev_init_nofail(DEVICE({dev_name}));
""".format(
    dev_name = dev_name,
    bus_name = self.node_map[node.parent_bus],
    qom_type = node.qom_type if Type.exists(node.qom_type) else "\"%s\"" % node.qom_type,
    props_code = props_code,
    multifunction = "true" if node.multifunction else "false",
    slot = node.slot,
    func = node.function
                    )
                else:
                    self.use_type_name("DeviceState")
                    if get_vp("use qdev_new"):
                        self.use_type_name("qdev_new")
                    else:
                        self.use_type_name("qdev_create")

                    decl_code += "    DeviceState *%s;\n" % dev_name

                    if Type.exists(node.qom_type):
                        qom_type = node.qom_type
                    else:
                        qom_type = "\"%s\"" % node.qom_type

                    if get_vp("use qdev_new"):
                        def_code += """\
    {dev_name} = qdev_new(@a{qom_type});{props_code}
""".format(
    dev_name = dev_name,
    qom_type = qom_type,
    props_code = props_code
                        )
                        if ((node.parent_bus is None)
                            or isinstance(node.parent_bus, SystemBusNode)
                        ):
                            self.use_type_name("sysbus_realize_and_unref")
                            self.use_type_name("SYS_BUS_DEVICE")
                            def_code += """\
    sysbus_realize_and_unref(@aSYS_BUS_DEVICE({dev_name}),@sNULL);
""".format(
    dev_name = dev_name
                            )
                        else:
                            # TODO: test this branch using some non-sysbus
                            #       configuration
                            self.use_type_name("qdev_realize_and_unref")
                            bus_name = \
                                "BUS(%s)" % self.node_map[node.parent_bus]
                            def_code += """\
    qdev_realize_and_unref(@a{dev_name},@s{bus_name},@sNULL);
""".format(
    dev_name = dev_name,
    bus_name = bus_name
                            )
                    else:
                        if ((node.parent_bus is None)
                            or isinstance(node.parent_bus, SystemBusNode)
                        ):
                            bus_name = "NULL"
                        else:
                            bus_name = \
                                "BUS(%s)" % self.node_map[node.parent_bus]

                        def_code += """\
    {dev_name} = qdev_create(@a{bus_name},@s{qom_type});{props_code}
    qdev_init_nofail({dev_name});
""".format(
    dev_name = dev_name,
    bus_name = bus_name,
    qom_type = qom_type,
    props_code = props_code
                        )

                if isinstance(node, SystemBusDeviceNode):
                    for idx, mmio in node.mmio_mappings.items():
                        if mmio is not None:
                            self.use_type_name("sysbus_mmio_map")
                            self.use_type_name("SYS_BUS_DEVICE")

                            if isinstance(mmio, str) and Type.exists(mmio):
                                self.use_type_name(mmio)
                                mmio_val = str(mmio)
                            else:
                                mmio_val = "0x%x" % mmio

                            def_code += """\
    sysbus_mmio_map(@aSYS_BUS_DEVICE({dev_name}),@s{idx},@s{mmio_val});
""".format(
    dev_name = dev_name,
    idx = idx,
    mmio_val = mmio_val
                            )

                for bus in node.buses:
                    if len(bus.devices) == 0:
                        continue

                    bus_name = self.node_map[bus]
                    try:
                        if isinstance(bus, PCIExpressBusNode):
                            if isinstance(node, SystemBusDeviceNode):
                                bridge_cast = "PCI_HOST_BRIDGE"
                                bus_field = "bus"
                            elif isinstance(node, PCIExpressDeviceNode):
                                bridge_cast = "PCI_BRIDGE"
                                bus_field = "sec_bus"
                            else:
                                raise UnknownBusBridgeType(node.parent_bus, bus)

                            self.use_type_name(bridge_cast)

                            def_code += """\
    {bus_name} = {bridge_cast}({bridge_name})->{bus_field};
""".format(
    bus_name = bus_name,
    bridge_name = dev_name,
    bridge_cast = bridge_cast,
    bus_field = bus_field
                            )
                        else:
                            raise UnknownBusBridgeType(node.parent_bus, bus)
                    except UnknownBusBridgeType:
                        self.use_type_name("qdev_get_child_bus")
                        self.use_type_name("DEVICE")
                        if bus.cast is not None:
                            self.use_type_name(bus.cast)

                        def_code += """\
    {bus_name} = {bus_cast};
""".format(
    bus_name = bus_name,
    bus_cast = ("(%s *) %%s" % bus.c_type) if bus.cast is None else ("%s(%%s)" % bus.cast),
                        ) % """\
qdev_get_child_bus(@aDEVICE({bridge_name}),@s"{bus_child_name}")\
""".format(
    bridge_name = dev_name,
    bus_child_name = bus.gen_child_name_for_bus(),
                        )

            elif isinstance(node, BusNode):
                # No definition code will be generated
                skip_nl = True

                if isinstance(node, SystemBusNode):
                    continue
                if len(node.devices) == 0:
                    continue

                self.use_type_name(node.c_type)

                bus_name = self.node_map[node]

                decl_code += "    %s *%s;\n" % (node.c_type, bus_name)
            elif isinstance(node, IRQLine):
                if node.hub_ended():
                    # Do not generate a code for IRQ lines that refers an IRQ
                    # hub. The code will be generated during the hub processing.
                    skip_nl = True
                    continue

                self.use_type_name("qemu_irq")

                irq_name = self.node_map[node]

                decl_code += "    qemu_irq %s;\n" % irq_name

                def_code += (
                    self.gen_irq_get(node.dst, irq_name)
                  + self.gen_irq_connect(node.src, irq_name)
                )
            elif isinstance(node, MemoryNode):
                self.use_type_name("MemoryRegion")
                if isinstance(node.size, str) and Type.exists(node.size):
                    self.use_type_name(node.size)
                if Type.exists(node.name):
                    self.use_type_name(node.name)

                mem_name = self.node_map[node]

                decl_code += "    MemoryRegion *%s;\n" % mem_name

                if isinstance(node, MemorySASNode):
                    self.use_type_name("get_system_memory")

                    def_code += "    %s = get_system_memory();\n" % mem_name
                else:
                    def_code += "    %s = g_new(MemoryRegion, 1);\n" % mem_name

                if isinstance(node, MemoryAliasNode):
                    self.use_type_name("memory_region_init_alias")
                    if Type.exists(node.alias_offset):
                        self.use_type_name(node.alias_offset)

                    def_code += """\
    memory_region_init_alias(@a{mem_name},@sNULL,@s{dbg_name},@s{orig},@s{offset},@s{size});
""".format(
    mem_name = mem_name,
    dbg_name = node.name if Type.exists(node.name) else "\"%s\"" % node.name,
    size = node.size,
    orig = self.node_map[node.alias_to],
    offset = node.alias_offset
                    )
                elif (isinstance(node, MemoryRAMNode)
                or isinstance(node, MemoryROMNode)
                ):
                    self.use_type_name("memory_region_init_ram")
                    if glob_mem:
                        self.use_type_name("vmstate_register_ram_global")

                    def_code += """\
    memory_region_init_ram(@a{mem_name},@sNULL,@s{dbg_name},@s{size},@sNULL);{glob}
""".format(
    mem_name = mem_name,
    dbg_name = node.name if Type.exists(node.name) else "\"%s\"" % node.name,
    size = node.size,
    glob = (("\n    vmstate_register_ram_global(%s);" % mem_name) if glob_mem
        else ""
    )
                    )
                elif not isinstance(node, MemorySASNode):
                    self.use_type_name("memory_region_init")

                    def_code += """\
    memory_region_init(@a{mem_name},@sNULL,@s{dbg_name},@s{size});
""".format(
    mem_name = mem_name,
    dbg_name = node.name if Type.exists(node.name) else "\"%s\"" % node.name,
    size = node.size
                    )

                if node.parent is not None:
                    if (isinstance(node.offset, str)
                    and Type.exists(node.offset)
                    ):
                        self.use_type_name(node.offset)
                    if node.may_overlap:
                        self.use_type_name("memory_region_add_subregion_overlap")
                        if (isinstance(node.priority, str)
                        and Type.exists(node.priority)
                        ):
                            self.use_type_name(node.priority)

                        def_code += """\
    memory_region_add_subregion_overlap(@a{parent_name},@s{offset},@s{child},@s{priority});
""".format(
    parent_name = self.node_map[node.parent],
    offset = node.offset,
    priority = node.priority,
    child = mem_name
                        )
                    else:
                        self.use_type_name("memory_region_add_subregion")
                        if (isinstance(node.priority, str)
                        and Type.exists(node.priority)
                        ):
                            self.use_type_name(node.priority)

                        def_code += """\
    memory_region_add_subregion(@a{parent_name},@s{offset},@s{child});
""".format(
    parent_name = self.node_map[node.parent],
    offset = node.offset,
    child = mem_name
                        )

            elif isinstance(node, IRQHub):
                if len(node.irqs) < 1:
                    # Nothing to do for detached IRQ hub
                    skip_nl = True
                    continue

                self.use_type_name("qemu_irq")

                hub_in_name = self.node_map[node]

                decl_code += "    qemu_irq %s;\n" % hub_in_name

                hubl = self.provide_hub_layout(node)

                code = hubl.gen_irq_get()
                decl_code += code[0]
                def_code += code[1]

                for in_irq in [irq for irq in node.irqs if irq.dst[0] == node]:
                    src = in_irq.src
                    if isinstance(src[0], IRQHub):
                        # A source hub does connects to this hub by itself
                        continue
                    def_code += self.gen_irq_connect(src, hub_in_name)
            elif isinstance(node, CPUNode):
                self.use_type_name("CPUState")
                self.use_type_name("cpu_create")
                self.use_type_name("qemu_register_reset")
                cpu_reset = self.cpu_reset
                self.use_type_name(cpu_reset.name)

                cpu_name = self.node_map[node]

                decl_code += "    CPUState *%s;\n" % cpu_name

                if Type.exists(node.qom_type):
                    qom_type = node.qom_type
                else:
                    qom_type = "\"%s\"" % node.qom_type

                def_code += """\
    {var_name}@b=@scpu_create(@a{qom_type});
    qemu_register_reset(@a{reset},@s{var_name});
""".format(
    var_name = cpu_name,
    qom_type = qom_type,
    reset = cpu_reset.name
                )
            else:
                raise UnknownMachineNodeType(str(type(node)))

        # machine initialization function
        self.instance_init = Type["MachineClass"].init.gen_callback(
            "init_%s" % self.qtn.for_id_name,
            body = decl_code + "\n" + def_code,
            static = True,
            used_types = self.init_used_types
        )
        self.source.add_type(self.instance_init)

        get_vp("machine type register template generator")(self)

    @cached
    def cpu_reset(self):
        cpu_reset = Type["QEMUResetHandler"].use_as_prototype(
            self.qtn.for_id_name + "_cpu_reset",
            body = BodyTree(),
            static = True
        )

        var_cpu = Pointer(Type["CPUState"])("cpu")

        cpu_reset.body = BodyTree()(
            Declare(OpDeclareAssign(
                var_cpu,
                MCall("CPU", cpu_reset.args[0])
            )),
            NewLine(),
            Call("cpu_reset", var_cpu)
        )

        self.source.add_type(cpu_reset)

        return cpu_reset

