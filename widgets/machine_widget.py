from Tkinter import \
    Label, \
    PanedWindow

from machine_diagram_widget import \
    MachineDiagramWidget

class MachineWidget(PanedWindow):
    def __init__(self, machine_description, *args, **kw):
        PanedWindow.__init__(self, *args, **kw)

        self.mach = machine_description

        self.pack(fill="both", expand="yes")

        # todo: replace with memory diagram
        l = Label(self,
            text = "A memory diagram will be here.".replace(" ", "\n")
        )
        self.add(l)

        self.mdw = MachineDiagramWidget(self, self.mach)
        self.add(self.mdw)
