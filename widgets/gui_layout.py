from copy import \
    deepcopy

class GUILayout(object):
    def __init__(self, desc_name, opaque):
        self.desc_name = desc_name
        self.opaque = opaque
        # ID of the layout
        self.lid = None;
        # cached widget reference
        self.widget = None

    def __deepcopy__(self, memo):
        ret = type(self)(self.desc_name, deepcopy(self.opaque, memo))
        ret.lid = self.lid
        return ret

    def sync_from_widget(self):
        if self.widget:
            self.opaque = self.widget.gen_layout()

    def __children__(self):
        return []

    def __gen_code__(self, g):
        g.reset_gen(self)
        g.gen_field("desc_name = " + g.gen_const(self.desc_name))
        g.gen_field("opaque = ")
        g.pprint(self.opaque)
        g.gen_end()

        if self.lid is not None:
            g.line(g.nameof(self) + ".lid = " + g.gen_const(self.lid))
