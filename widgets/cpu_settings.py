__all__ = [
    "CPUSettingsWindow"
  , "CPUSettingsWidget"
]

from .settings_window import (
    SettingsWindow,
    QOMInstanceSettingsWidget
)
from common import (
    mlget as _
)
from qemu import (
    MachineNodeOperation
)
from .var_widgets import (
    VarLabel
)
from six.moves.tkinter import (
    BOTH,
    StringVar
)
from qemu import (
    MOp_SetCPUAttr
)
from .hotkey import (
    HKEntry
)
from .gui_frame import (
    GUIFrame
)


class CPUSettingsWidget(QOMInstanceSettingsWidget):

    def __init__(self, cpu, *args, **kw):
        QOMInstanceSettingsWidget.__init__(self, cpu, *args, **kw)

        self.cpu = cpu

        self.cpu_fr = fr = GUIFrame(self)
        fr.pack(fill = BOTH, expand = False)

        fr.columnconfigure(0, weight = 0)
        fr.columnconfigure(1, weight = 1)
        fr.rowconfigure(0, weight = 0)

        l = VarLabel(fr, text = _("QOM type"))
        v = self.qom_type_var = StringVar()
        e = HKEntry(fr, textvariable = v)
        v.trace_variable("w", self._on_qom_type_var_changed)

        l.grid(row = 0, column = 0, sticky = "W")
        e.grid(row = 0, column = 1, sticky = "EW")

    def __apply_internal__(self):
        qom = self.qom_type_var.get()
        if self.cpu.qom_type == qom:
            return 

        self.mht.stage(MOp_SetCPUAttr, "qom_type", qom, self.cpu.id)

        self.mht.set_sequence_description(
            _("CPU %d configuration.") % self.cpu.id
        )

    def refresh(self):
        QOMInstanceSettingsWidget.refresh(self)

        self.qom_type_var.set(self.cpu.qom_type)

    def on_changed(self, op, *__, **___):
        if not isinstance(op, MachineNodeOperation):
            return

        if op.writes_node():
            if not self.cpu.id in self.mach.id2node:
                self.destroy()
            else:
                self.refresh()


class CPUSettingsWindow(SettingsWindow):

    def __init__(self, cpu, *args, **kw):
        SettingsWindow.__init__(self, cpu, *args, **kw)

        self.title(_("CPU settings"))

        self.set_sw(CPUSettingsWidget(cpu, self.mach, self))
        self.sw.grid(row = 0, column = 0, sticky = "NEWS")
