__all__ = [
    "MachineWidgetLayout"
  , "MachineDescriptionSettingsWidget"
  , "MachineTabsWidget"
  , "MachinePanedWidget"
]

from six.moves.tkinter import (
    VERTICAL,
    StringVar,
    Spinbox,
    BooleanVar,
    PanedWindow
)
from six.moves.tkinter_ttk import (
    Separator
)
from .machine_diagram_widget import (
    MIN_MESH_STEP,
    MAX_MESH_STEP,
    MachineDiagramWidget
)
from .qom_settings import (
    QOMDescriptionSettingsWidget
)
from .memory_tree_widget import (
    MemoryTreeWidget
)
from .var_widgets import (
    VarLabel,
    VarCheckbutton,
    VarNotebook
)
from common import (
    mlget as _
)

class MachineWidgetLayout(object):
    """
    mtwl = Memory Tree Widget Layout
    mdwl = Machine Diagram Widget Layout
    """
    def __init__(self, mdwl, mtwl, use_tabs = True):
        self.mdwl, self.mtwl, self.use_tabs = mdwl, mtwl, use_tabs

    def __gen_code__(self, g):
        g.reset_gen(self)
        g.gen_field("mdwl = ")
        g.pprint(self.mdwl)
        g.gen_field("mtwl = ")
        g.pprint(self.mtwl)
        g.gen_field("use_tabs = " + g.gen_const(self.use_tabs))
        g.gen_end()

class MachinePanedWidget(PanedWindow):
    def __init__(self, machine_description, *args, **kw):
        PanedWindow.__init__(self, *args, **kw)

        self.mach = machine_description

        self.pack(fill="both", expand="yes")

        self.mtw = MemoryTreeWidget(self.mach, self)
        self.add(self.mtw)

        self.mdw = MachineDiagramWidget(self, self.mach)
        self.add(self.mdw)

class MachineTabsWidget(VarNotebook):
    def __init__(self, machine_description, *args, **kw):
        VarNotebook.__init__(self, *args, **kw)

        self.mach = machine_description

        self.pack(fill="both", expand="yes")

        self.mdw = MachineDiagramWidget(self, self.mach)
        self.add(self.mdw, text = "Device diagram")

        self.mtw = MemoryTreeWidget(self.mach, self)
        self.add(self.mtw, text = "Memory")

class MachineDescriptionSettingsWidget(QOMDescriptionSettingsWidget):
    def __init__(self, *args, **kw):
        QOMDescriptionSettingsWidget.__init__(self, *args, **kw)

        self.mw = None

        self.var_tabs = v = BooleanVar()
        self.buttons_fr.columnconfigure(2, weight = 0)
        chb = VarCheckbutton(self.buttons_fr,
            text = _("Use tabs"),
            variable = v
        )
        chb.grid(row = 0, column = 2, sticky = "NEWS")
        v.trace_variable("w", self.__on_tabs__)

        # mesh step seleection
        self.buttons_fr.columnconfigure(3, weight = 0)
        self.buttons_fr.columnconfigure(4, weight = 0)
        self.buttons_fr.columnconfigure(5, weight = 0)

        Separator(self.buttons_fr, orient = VERTICAL).grid(
            row = 0,
            column = 3,
            sticky = "NEWS"
        )

        l = VarLabel(self.buttons_fr, text = _("Mesh step:"))
        l.grid(row = 0, column = 4, sticky = "NEWS")

        self.var_mesh_step = v = StringVar()
        v.trace_variable("w", self.__on_mesh_step)
        self.mesh_step_sb = sb = Spinbox(self.buttons_fr,
            from_ = MIN_MESH_STEP,
            to = MAX_MESH_STEP,
            textvariable = v,
            width = len(str(MAX_MESH_STEP))
        )
        sb.grid(row = 0, column = 5, sticky = "NEWS")

        self.var_tabs.set(True)

    def __on_mesh_step(self, *args):
        val = self.var_mesh_step.get()

        if self.mw is None:
            return

        try:
            step = int(val)
        except ValueError:
            return

        if step < MIN_MESH_STEP:
            step = MIN_MESH_STEP
            self.var_mesh_step.set(MIN_MESH_STEP)
        elif step > MAX_MESH_STEP:
            step = MAX_MESH_STEP
            self.var_mesh_step.set(MAX_MESH_STEP)

        self.mw.mdw.mesh_step.set(step)

    def __on_tabs__(self, *args):
        use_tabs = self.var_tabs.get()

        if use_tabs != isinstance(self.mw, MachineTabsWidget):
            if self.mw is None:
                layout = [ {}, None ]
            else:
                layout = [ w.gen_layout() for w in [self.mw.mdw, self.mw.mtw] ]
                self.mw.destroy()

            # 'self' is used as master widget (instead of self.settings_fr)
            # because buttons is only affects inherited fields. Changes to
            # the machine and its memory diagrams is handled by diagrams itself
            self.mw = (MachineTabsWidget if use_tabs else MachinePanedWidget) \
                (self.desc, self)

            self.mw.pack()

            for w, l in zip([self.mw.mdw, self.mw.mtw], layout):
                w.set_layout(l)

            self.var_mesh_step.set(self.mw.mdw.mesh_step.get())

    def gen_layout(self):
        return MachineWidgetLayout(
            self.mw.mdw.gen_layout(),
            self.mw.mtw.gen_layout(),
            use_tabs = isinstance(self.mw, MachineTabsWidget)
        )

    def set_layout(self, layout):
        if isinstance(layout, MachineWidgetLayout):
            self.var_tabs.set(layout.use_tabs)
            self.mw.mdw.set_layout(layout.mdwl)
            self.mw.mtw.set_layout(layout.mtwl)
        else: # Previous version compatibility
            try:
                extra = layout[-1]
            except KeyError:
                use_tabs = True
            else:
                try:
                    use_tabs = extra.pop("use tabs")
                except KeyError:
                    use_tabs = True

            self.var_tabs.set(use_tabs)
            self.mw.mdw.set_layout(layout)
            self.mw.mtw.set_layout(None)

        self.var_mesh_step.set(self.mw.mdw.mesh_step.get())

    def __apply_internal__(self):
        # There is nothing to apply additionally
        pass
