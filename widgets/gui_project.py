__all__ = [
    "GUIProject"
]

from common import (
    History,
)
from .gui_layout import (
    GUILayout,
)
from qemu import (
    MachineNode,
    QProject,
    QType,
)

from itertools import (
    count,
)


class GUIProject(QProject):

    def __init__(self,
        layouts = [],
        build_path = None,
        target_version = None,
        **kw
    ):
        # Any description in GUI project has a serial number.
        self.__next_id = 0

        QProject.__init__(self, **kw)

        self.build_path = build_path
        self.target_version = target_version

        self.layouts = {}
        for l in layouts:
            # backward compatibility
            if isinstance(l, tuple):
                self.add_layout(*l)
                continue

            dn = l.desc_name
            try:
                l_dict = self.layouts[dn]
            except KeyError:
                self.layouts[dn] = l_dict = {}
            l_dict[l.lid] = l

        self.history = History()
        self.reset_qom_tree()

    def reset_qom_tree(self):
        self.qom_tree = q_root = QType("[QOM root is not a type]")

        q_object = QType("object")
        q_root.add_child(q_object)

        q_machine = QType("machine")
        q_object.add_child(q_machine)

        q_device = QType("device")
        q_object.add_child(q_device)

        q_sys_bus_device = QType("sys-bus-device")
        q_device.add_child(q_sys_bus_device)

        q_pci_device = QType("pci-device")
        q_device.add_child(q_pci_device)

        q_cpu = QType("cpu")
        q_device.add_child(q_cpu)

    def add_layout_object_auto_id(self, l):
        try:
            l_dict = self.layouts[l.desc_name]
        except KeyError:
            l.lid = 0
        else:
            for lid in count(0):
                if lid not in l_dict:
                    l.lid = lid
                    break

        self.add_layout_object(l)

    def add_layout_object(self, l):
        try:
            l_dict = self.layouts[l.desc_name]
        except KeyError:
            self.layouts[l.desc_name] = l_dict = {}
        if l.lid in l_dict:
            raise Exception("Layout with id %d for description '%s' already \
exists." % (l.lid, l.desc_name)
            )
        l_dict[l.lid] = l

    def add_layout_objects(self, lys):
        for l in lys:
            self.add_layout_object(l)

    def add_layout(self, desc_name, layout_opaque):
        l = GUILayout(desc_name, layout_opaque)
        self.add_layout_object_auto_id(l)
        return l

    def delete_layouts(self, desc_name):
        del self.layouts[desc_name]

    def rename_layouts(self, prev_desc_name, desc_name):
        if desc_name in self.layouts:
            raise ValueError("Layouts for %s are already exist" % desc_name)

        if prev_desc_name in self.layouts:
            lys = self.layouts.pop(prev_desc_name)
            self.layouts[desc_name] = lys
            for l in lys.values():
                l.desc_name = desc_name

    # replaces all layouts for description with new layout
    def set_layout(self, desc_name, layout_opaque):
        self.delete_layouts(desc_name)
        self.add_layout(desc_name, layout_opaque)

    def set_layouts(self, desc_name, layout_opaques):
        self.delete_layouts(desc_name)

        for lo in layout_opaques:
            self.add_layout(desc_name, lo)

    def get_layouts(self, desc_name):
        return [ l.opaque for l in self.get_layout_objects(desc_name) ]

    def get_layout_objects(self, desc_name):
        try:
            lys = self.layouts[desc_name]
        except KeyError:
            return []
        # explicit list conversion is used for Python 3.x compatibility
        return list(lys.values())

    def get_machine_descriptions(self):
        return [ d for d in self.descriptions if isinstance(d, MachineNode) ]

    def get_all_layouts(self):
        return [
            l for ld in self.layouts.values() for l in ld.values()
        ]

    def get_all_layouts_sorted(self):
        return sorted(self.get_all_layouts(),
            key = lambda l: (l.desc_name, l.lid)
        )

    __pygen_deps__ = QProject.__pygen_deps__ + ("layouts",)

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field("layouts = ")
        gen.pprint(self.get_all_layouts_sorted())
        gen.gen_field("build_path = " + gen.gen_const(self.build_path))
        if self.target_version is not None:
            gen.gen_field("target_version = " + gen.gen_const(
                self.target_version
            ))
        gen.gen_field("descriptions = ")
        gen.pprint(self.descriptions)
        gen.gen_end()

    def next_serial_number(self):
        ret = self.__next_id
        self.__next_id = ret + 1
        return ret

    def add_description(self, desc, with_sn = None):
        if hasattr(desc, "__sn__"):
            raise RuntimeError("The description has a serial number already")

        if with_sn is None:
            with_sn = self.next_serial_number()
        elif with_sn >= self.__next_id:
            self.__next_id = with_sn + 1

        desc.__sn__ = with_sn

        QProject.add_description(self, desc)

    def remove_description(self, desc):
        QProject.remove_description(self, desc)
        del desc.__sn__

    @staticmethod
    def from_qproject(qproj):
        guiproj = GUIProject()
        for d in list(qproj.descriptions):
            d.remove_from_project()

            if isinstance(d, MachineNode):
                d.link()

            guiproj.add_description(d)

        return guiproj

    def sync_layouts(self):
        for desc_layouts in self.layouts.values():
            for l in desc_layouts.values():
                l.sync_from_widget()
                # "shown" from opaque dictionary is not more relevant while
                # its attribute analog is maintained dynamically.
