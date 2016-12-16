from qemu import \
    MachineNode, \
    QProject

from gui_proj_ht import \
    GUIProjectHistoryTracker

from common import \
    History

from gui_layout import \
    GUILayout

from itertools import \
    count

class GUIProject(QProject):
    def __init__(self, layouts = [], build_path = None, **kw):
        QProject.__init__(self, **kw)

        self.build_path = build_path

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

        self.pht = GUIProjectHistoryTracker(self, History())

    def add_layout_object_auto_id(self, l):
        try:
            l_dict = self.layouts[l.desc_name]
        except KeyError:
            self.layouts[l.desc_name] = l_dict = {}
        for lid in count(0):
            if lid not in l_dict:
                l.lid = lid
                l_dict[lid] = l
                break

    def add_layout(self, desc_name, layout_opaque):
        l = GUILayout(desc_name, layout_opaque)
        self.add_layout_object_auto_id(l)

    def delete_layouts(self, desc_name):
        del self.layouts[desc_name]

    # replaces all layouts for description with new layout
    def set_layout(self, desc_name, layout_opaque):
        self.delete_layouts(desc_name)
        self.add_layout(desc_name, layout_opaque)

    def set_layouts(self, desc_name, layout_opaques):
        self.delete_layouts(desc_name)

        for lo in layout_opaques:
            self.add_layout(desc_name, lo)

    def get_layouts(self, desc_name):
        try:
            lys = self.layouts[desc_name]
        except KeyError:
            return []
        return [ l.opaque for l in lys.values() ]

    def get_machine_descriptions(self):
        return [ d for d in self.descriptions if isinstance(d, MachineNode) ]

    def get_all_layouts(self):
        return [
            l for ld in self.layouts.values() for l in ld.values()
        ]

    def __children__(self):
        return list(self.descriptions) + self.get_all_layouts()

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field("layouts = ")
        gen.pprint(self.get_all_layouts())
        gen.gen_field("build_path = " + gen.gen_const(self.build_path))
        gen.gen_field("descriptions = [")
        gen.line()
        gen.push_indent()
        for i, desc in enumerate(self.descriptions):
            if i > 0:
                gen.line(",")
            gen.write(gen.nameof(desc))
        gen.line()
        gen.pop_indent()
        gen.write("]")
        gen.gen_end()

