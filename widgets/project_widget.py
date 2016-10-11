from var_widgets import \
    VarTreeview

from ttk import \
    Notebook

from machine_widget import \
    MachineWidget

from qemu import \
    MachineNode

from Tkinter import \
    PanedWindow

from common import \
    ML as _

class DescriptionsTreeview(VarTreeview):
    def __init__(self, descriptions, *args, **kw):
        VarTreeview.__init__(self, *args, **kw)

        self.descs = descriptions

        self.heading("#0", text = _("Name"))

        self.after(0, self.update)

    def update(self):
        self.delete(*self.get_children())

        for i, d in enumerate(self.descs):
            self.insert('', i, text = d.name)

class ProjectWidget(PanedWindow):
    def __init__(self, project, *args, **kw):
        PanedWindow.__init__(self, *args, **kw)

        self.p = project

        self.tv_descs = DescriptionsTreeview(self.p.descriptions)
        self.add(self.tv_descs)

        self.nb_descriptions = Notebook(self)
        self.add(self.nb_descriptions)

        self.desc2w = {}
        for desc in self.p.descriptions:
            widgets = self.desc2w[desc] = []

            for l in self.p.get_layouts(desc.name):
                try:
                    cfg = l[-1]
                except KeyError:
                    l[-1] = cfg = {}

                try:
                    if not cfg["shown"]:
                        continue
                except KeyError:
                    # by default the layout is shown
                    pass

                w = self.gen_widget(desc)
                try:
                    w.set_layout(l)
                except:
                    w.destroy()
                    w = None
                else:
                    widgets.append(w)

                    self.nb_descriptions.add(w, text = desc.name)

    def refresh_layouts(self):
        for desc, widgets in self.desc2w.iteritems():

            layouts = []
            for w in widgets:
                l = w.gen_layout()
                try:
                    cfg = l[-1]
                except KeyError:
                    l[-1] = cfg = {}

                cfg["shown"] = True

                layouts.append(l)

            old_layouts = [ e for e in self.p.layouts if e[0] == desc.name ]

            if layouts:
                if old_layouts:
                    self.p.layouts.remove(*old_layouts)
    
                for l in layouts:
                    self.p.layouts.append((desc.name, l))
            else:
                for n, l in old_layouts:
                    try:
                        cfg = l[-1]
                    except KeyError:
                        continue
                    try:
                        cfg["shown"] = False
                    except KeyError:
                        pass

    def undo(self):
        self.p.pht.undo_sequence()

    def redo(self):
        self.p.pht.do_sequence()

    def can_do(self):
        return self.p.pht.can_do()

    def can_redo(self):
        return self.p.pht.can_do()

    def gen_widget(self, desc):
        if isinstance(desc, MachineNode):
            w = MachineWidget(desc, self)
        else:
            raise Exception("No widget exists for description %s of type %s." %
                    (desc.name, type(desc).__name__)
                )
        return w
