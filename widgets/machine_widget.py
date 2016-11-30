from Tkinter import \
    Label, \
    PanedWindow

from machine_diagram_widget import \
    MachineDiagramWidget

from qom_settings import \
    QOMDescriptionSettingsWidget

from memory_tree_widget import \
    MemoryTreeWidget

from var_widgets import \
    VarNotebook

from common import \
    mlget as _

class MachinePanedWidget(PanedWindow):
    def __init__(self, machine_description, *args, **kw):
        PanedWindow.__init__(self, *args, **kw)

        self.mach = machine_description

        self.pack(fill="both", expand="yes")

        self.mtw = MemoryTreeWidget(self.mach)
        self.add(self.mtw)

        self.mdw = MachineDiagramWidget(self, self.mach)
        self.add(self.mdw)

    def gen_layout(self):
        return self.mdw.gen_layout()

    def set_layout(self, layout):
        self.mdw.set_layout(layout)

class MachineTabsWidget(VarNotebook):
    def __init__(self, machine_description, *args, **kw):
        VarNotebook.__init__(self, *args, **kw)

        self.mach = machine_description

        self.pack(fill="both", expand="yes")

        self.mdw = MachineDiagramWidget(self, self.mach)
        self.add(self.mdw, text = "Device diagram")

        self.mtw = MemoryTreeWidget(self.mach)
        self.add(self.mtw, text = "Memory")

    def gen_layout(self):
        return self.mdw.gen_layout()

    def set_layout(self, layout):
        self.mdw.set_layout(layout)

class MachineDescriptionSettingsWidget(QOMDescriptionSettingsWidget):
    def __init__(self, *args, **kw):
        QOMDescriptionSettingsWidget.__init__(self, *args, **kw)

        # 'self' is used as master widget (instead of self.settings_fr)
        # because buttons is only affects inherited fields. Changes to
        # the machine and its memory diagrams is handled by diagrams itself  
        self.mw = MachineTabsWidget(self.desc, self)
        self.mw.pack()

    def gen_layout(self):
        layout = self.mw.gen_layout()

        try:
            extra = layout[-1]
        except KeyError:
            layout[-1] = extra = {}

        extra["use tabs"] = isinstance(self.mw, MachineTabsWidget)

        return layout

    def set_layout(self, layout):
        try:
            extra = layout[-1]
        except KeyError:
            use_tabs = True
        else:
            try:
                use_tabs = extra.pop("use tabs")
            except KeyError:
                use_tabs = True

        if use_tabs != isinstance(self.mw, MachineTabsWidget):
            self.mw.destroy()
            self.mw = (MachineTabsWidget if use_tabs else MachinePanedWidget) \
                (self.desc, self)
            self.mw.pack()

        self.mw.set_layout(layout)

    def __apply_internal__(self):
        # There is nothing to apply additionally
        pass
