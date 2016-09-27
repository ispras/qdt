from qemu import \
    ProjectHistoryTracker, \
    MachineNode, \
    QProject

from common import \
    History

class GUIProject(QProject):
    def __init__(self, layouts = [], **kw):
        QProject.__init__(self, **kw)

        self.layouts = layouts
        self.pht = ProjectHistoryTracker(self, History())

    def get_layouts(self, desc_name):
        return [ l for name, l in self.layouts if name == desc_name ]

    def get_machine_descriptions(self):
        return [ d for d in self.descriptions if isinstance(d, MachineNode) ]

    def __children__(self):
        return list(self.descriptions)

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field("layouts = ")
        gen.pprint(self.layouts)
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

