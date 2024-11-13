__all__ = [
    "CPUSettingsWindow"
  , "CPUSettingsWidget"
]

from common import (
    mlget as _,
)
from .gui_frame import (
    GUIFrame,
)
from .hotkey import (
    HKEntry,
)
from qemu import (
    MachineNodeOperation,
    MOp_SetCPUAttr,
)
from .device_tree_widget import (
    QOMTypeSelectDialog,
)
from .settings_window import (
    QOMInstanceSettingsWidget,
    SettingsWindow,
)
from .var_widgets import (
    VarButton,
    VarLabel,
)

from six.moves.tkinter import (
    BOTH,
    StringVar,
)


# `object` is for `property`
class CPUSettingsWidget(QOMInstanceSettingsWidget, object):

    def __init__(self, *args, **kw):
        kw["node"] = kw.pop("cpu")
        QOMInstanceSettingsWidget.__init__(self, *args, **kw)

        self.cpu_fr = fr = GUIFrame(self)
        fr.pack(fill = BOTH, expand = False)

        fr.columnconfigure(0, weight = 0)
        fr.columnconfigure(1, weight = 1)
        fr.columnconfigure(2, weight = 0)
        fr.rowconfigure(0, weight = 0)

        l = VarLabel(fr, text = _("QOM type"))
        v = self.qom_type_var = StringVar()
        e = HKEntry(fr, textvariable = v)
        v.trace_variable("w", self._on_qom_type_var_changed)

        b = VarButton(fr,
            text = _("Select"),
            command = self.on_press_select_qom_type
        )
        b.grid(row = 0, column = 2, sticky = "EW")

        l.grid(row = 0, column = 0, sticky = "W")
        e.grid(row = 0, column = 1, sticky = "EW")

    @property
    def cpu(self):
        return self.node

    def __apply_internal__(self):
        cpu = self.node

        qom = self.qom_type_var.get()
        if cpu.qom_type == qom:
            return

        self.mht.stage(MOp_SetCPUAttr, "qom_type", qom, cpu.id)

        self.mht.set_sequence_description(
            _("CPU %d configuration.") % cpu.id
        )

    def refresh(self):
        QOMInstanceSettingsWidget.refresh(self)

        self.qom_type_var.set(self.node.qom_type)

    def on_changed(self, op, *__, **___):
        if not isinstance(op, MachineNodeOperation):
            return

        if op.writes_node():
            if self.node.id not in self.mach.id2node:
                self.destroy()
            else:
                self.refresh()

    def on_press_select_qom_type(self):
        device_tree = next(self.mach.project.qom_tree.find(name = "cpu"))

        device_type = QOMTypeSelectDialog(self, qom_tree = device_tree).wait()
        if device_type:
            self.qom_type_var.set(device_type)


class CPUSettingsWindow(SettingsWindow):

    def __init__(self, *args, **kw):
        kw["node"] = cpu = kw.pop("cpu")
        SettingsWindow.__init__(self, *args, **kw)

        self.title(_("CPU settings"))

        self.set_sw(CPUSettingsWidget(self,
            cpu = cpu,
            machine = self.mach,
        ))
        self.sw.grid(row = 0, column = 0, sticky = "NEWS")
