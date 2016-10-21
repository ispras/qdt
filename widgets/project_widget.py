from var_widgets import \
    VarTreeview

from close_button_notebook import \
    CloseButtonNotebook

from machine_widget import \
    MachineDescriptionSettingsWidget

from qemu import \
    SysBusDeviceDescription, \
    MachineNode

from Tkinter import \
    PanedWindow

from common import \
    mlget as _

from qemu import \
    POp_AddDesc

from sysbusdev_description_settings import \
    SystemBusDeviceDescriptionSettingsWidget

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

        self.nb_descriptions = CloseButtonNotebook(self)
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

        self.tv_descs.bind("<Double-1>", self.on_tv_desc_b1_double)

        self.nb_descriptions.bind("<<NotebookTabClosed>>",
            self.on_notebook_tab_closed)

        self.p.pht.add_on_changed(self.on_project_changed)

    def on_project_changed(self, op):
        if isinstance(op, POp_AddDesc):
            self.tv_descs.update()

            for desc, wl in self.desc2w.iteritems():
                if desc not in self.p.descriptions:
                    # removed
                    for w in wl:
                        w.destroy()
                    del self.desc2w[desc]
                    break
            else:
                for desc in self.p.descriptions:
                    if desc not in self.desc2w:
                        # added
                        self.desc2w[desc] = []
                        break

    def on_notebook_tab_closed(self, event):
        tabs = [ self.nametowidget(w) for w in self.nb_descriptions.tabs() ] 
        for widgets in self.desc2w.values():
            for w in list(widgets):
                if w not in tabs:
                    widgets.remove(w)

    def on_tv_desc_b1_double(self, event):
        try:
            item = self.tv_descs.selection()[0]
        except IndexError:
            # nothing is selected
            return

        name = self.tv_descs.item(item)["text"]

        for desc in self.p.descriptions:
            if desc.name == name:
                break

        widgets = self.desc2w[desc]

        if not widgets:
            w = self.gen_widget(desc)

            widgets.append(w)

            layouts = self.p.get_layouts(desc.name)
            if layouts:
                w.set_layout(layouts[0])

            self.nb_descriptions.add(w, text = desc.name)
            for tab_id in self.nb_descriptions.tabs():
                if self.nb_descriptions.tab(tab_id)["text"] == desc.name:
                    break
            self.nb_descriptions.select(tab_id)
        else:
            # select next widget
            tab_id = self.nb_descriptions.select()
            w = self.nametowidget(tab_id)
            if w in widgets:
                i = widgets.index(w)
                next_w = widgets[(i + 1) % len(widgets)]
            else:
                next_w = widgets[0]
            self.nb_descriptions.select(next_w)

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
            w = MachineDescriptionSettingsWidget(desc, self.p.pht, self)
        elif isinstance(desc, SysBusDeviceDescription):
            w = SystemBusDeviceDescriptionSettingsWidget(desc, self.p.pht, self)
        else:
            raise Exception("No widget exists for description %s of type %s." %
                    (desc.name, type(desc).__name__)
                )
        return w
