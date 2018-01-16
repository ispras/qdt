from .settings_window import (
    SettingsWidget,
    SettingsWindow
)
from common import mlget as _

from .var_widgets import (
    VarLabelFrame,
    VarLabel
)
from qemu import (
    MOp_SetIRQAttr,
    MOp_SetIRQEndPoint,
    MachineNodeOperation,
    DeviceNode
)
from six.moves import range as xrange

from six.moves.tkinter import (
    BOTH,
    StringVar
)
from six.moves.tkinter_ttk import Combobox

from .device_settings import DeviceSettingsWidget

from .hotkey import HKEntry

class IRQSettingsWidget(SettingsWidget):
    def __init__(self, irq, *args, **kw):
        SettingsWidget.__init__(self, irq, *args, **kw)

        self.irq = irq

        for pfx, txt in [
            ("src_", _("Source")),
            ("dst_", _("Destination"))
        ]:
            lf = VarLabelFrame(self, text = txt)
            lf.pack(fill = BOTH, expand = False)

            lf.columnconfigure(0, weight = 0)
            lf.columnconfigure(1, weight = 1)

            for row in xrange(0, 3):
                lf.rowconfigure(row, weight = 1)

            l = VarLabel(lf, text = _("Node"))
            l.grid(row = 0, column = 0, sticky = "NE")

            node_var = StringVar()
            node_var.trace_variable("w", self.on_node_text_changed)
            node_cb = Combobox(lf,
                textvariable = node_var,
                values = [],
                state = "readonly"
            )
            node_cb.grid(row = 0, column = 1, sticky = "NEW")

            irq_idx_l = VarLabel(lf, text = _("GPIO index"))
            irq_idx_l.grid(row = 1, column = 0, sticky = "NE")

            irq_idx_var = StringVar()
            irq_idx_e = HKEntry(lf, textvariable = irq_idx_var)
            irq_idx_e.grid(row = 1, column = 1, sticky = "NEW")

            irq_name_l = VarLabel(lf, text = _("GPIO name"))
            irq_name_l.grid(row = 2, column = 0, sticky = "NE")

            irq_name_var = StringVar()
            irq_name_e = HKEntry(lf, textvariable = irq_name_var)
            irq_name_e.grid(row = 2, column = 1, sticky = "NEW")

            for v in ["lf", "node_var", "node_cb",
                      "irq_idx_l", "irq_idx_e", "irq_idx_var",
                      "irq_name_l", "irq_name_e", "irq_name_var"]:
                setattr(self, pfx + v, locals()[v])

        self.__auto_var_base_cbs = None
        self.v_var_base.trace_variable("w", self.__on_var_base)

    def __on_var_base(self, *args):
        cbs = self.__auto_var_base_cbs

        if cbs is None:
            if self.v_var_base.get() == self.get_auto_irq_var_base():
                self.__auto_var_base_cbs = (
                    self.src_node_var.trace_variable("w", self.__auto_var_base),
                    self.dst_node_var.trace_variable("w", self.__auto_var_base),
                    self.src_irq_idx_var.trace_variable("w",
                        self.__auto_var_base
                    ),
                    self.dst_irq_idx_var.trace_variable("w",
                        self.__auto_var_base
                    )
                )
        else:
            if self.v_var_base.get() != self.get_auto_irq_var_base():
                self.__auto_var_base_cbs = None

                self.src_node_var.trace_vdelete("w", cbs[0])
                self.dst_node_var.trace_vdelete("w", cbs[1])
                self.src_irq_idx_var.trace_vdelete("w", cbs[2])
                self.dst_irq_idx_var.trace_vdelete("w", cbs[3])

    def on_node_text_changed(self, *args):
        irq = self.irq

        for pfx in [ "src", "dst" ]:
            node_var = getattr(self, pfx + "_node_var")
            node_text = node_var.get()

            if not node_text:
                continue

            node = self.find_node_by_link_text(node_text)
            node_is_device = isinstance(node, DeviceNode)

            irq_idx_l = getattr(self, pfx + "_irq_idx_l")
            irq_idx_e = getattr(self, pfx + "_irq_idx_e")
            irq_name_l = getattr(self, pfx + "_irq_name_l")
            irq_name_e = getattr(self, pfx + "_irq_name_e")

            dev_widgets = [irq_idx_l, irq_idx_e, irq_name_l, irq_name_e]

            if getattr(self, pfx + "_is_device") != node_is_device:
                setattr(self, pfx + "_is_device", node_is_device)

                # node kind was changed
                if node_is_device:
                    for w in dev_widgets:
                        w.config(state = "normal")

                    irq_idx = getattr(irq, pfx + "_irq_idx")
                    getattr(self, pfx + "_irq_idx_var").set(str(irq_idx))

                    irq_name = getattr(irq, pfx + "_irq_name")
                    if irq_name is None:
                        irq_name = ""

                    getattr(self, pfx + "_irq_name_var").set(irq_name)

                else:
                    for w in dev_widgets:
                        w.config(state = "disabled")

                    getattr(self, pfx + "_irq_idx_var").set("")
                    getattr(self, pfx + "_irq_name_var").set("")

    def __apply_internal__(self):
        irq = self.irq

        for pfx in [ "src", "dst" ]:
            var = getattr(self, pfx + "_node_var")
            new_val = self.find_node_by_link_text(var.get()) 

            cur_val = getattr(irq, pfx + "_node")

            if new_val is not cur_val:
                self.mht.stage(
                    MOp_SetIRQEndPoint,
                    pfx + "_node",
                    new_val,
                    irq.id
                )

            for attr in [ "irq_idx", "irq_name" ]:
                var = getattr(self, pfx + "_" + attr + "_var")
                new_val = var.get()
                if not new_val:
                    if attr is "irq_idx":
                        new_val = 0
                    else:
                        new_val = None

                cur_val = getattr(irq, pfx + "_" +attr)

                if attr is "irq_idx":
                    cur_type = type(cur_val)
                    try: # to preserve current value type
                        new_val = cur_type(new_val)
                    except ValueError:
                        cur_val = str(cur_val)

                if not new_val == cur_val:
                    self.mht.stage(
                        MOp_SetIRQAttr,
                        pfx + "_" + attr,
                        new_val,
                        irq.id
                    )

        self.mht.set_sequence_description(_("IRQ line configuration."))

    def refresh(self):
        SettingsWidget.refresh(self)

        nodes = [ DeviceSettingsWidget.gen_node_link_text(node) \
            for node in self.mach.devices + self.mach.irq_hubs ]

        for pfx in [ "src", "dst" ]:
            cb = getattr(self, pfx + "_node_cb")
            cb.config(values = nodes)

            # IRQ line end (source or destination)
            end_node = getattr(self.irq, pfx + "_dev")
            node_text = DeviceSettingsWidget.gen_node_link_text(end_node)
            node_var = getattr(self, pfx + "_node_var")

            is_device = isinstance(end_node, DeviceNode)
            """ Intentionally invert value of `[src/dst]_is_device` to cause
            `on_node_text_changed` to update index and name fields in course of
            `node_var` setting trace call. """
            setattr(self, pfx + "_is_device", not is_device)

            node_var.set(node_text)

        # If current var base equals auto var base then turn auto var base
        # suggestion on.
        self.__on_var_base()

    def on_changed(self, op, *args, **kw):
        if not isinstance(op, MachineNodeOperation):
            return

        if op.writes_node():
            if not self.irq.id in self.mach.id2node:
                self.destroy()
            else:
                self.refresh()
        elif isinstance(op, MOp_SetIRQAttr):
            if op.node_id == self.irq.id:
                self.refresh()

    def __auto_var_base(self, *args):
        self.v_var_base.set(self.get_auto_irq_var_base())

    def get_auto_irq_var_base(self):
        try:
            node_id2var_name = self.mach.node_id2var_name
        except AttributeError:
            return "irq"

        if self.src_node_var.get() == "" or self.dst_node_var.get() == "":
            return "irq"

        try:
            src_idx = int(self.src_irq_idx_var.get())
            dst_idx = int(self.dst_irq_idx_var.get())
        except ValueError:
            return "irq"

        src_id = self.find_node_by_link_text(self.src_node_var.get()).id
        dst_id = self.find_node_by_link_text(self.dst_node_var.get()).id

        return "irq_%s_%u_to_%s_%u" % (
            node_id2var_name[src_id].get(),
            src_idx,
            node_id2var_name[dst_id].get(),
            dst_idx,
        )

class IRQSettingsWindow(SettingsWindow):
    def __init__(self, *args, **kw):
        irq = kw.pop("irq")

        SettingsWindow.__init__(self, irq, *args, **kw)

        self.title(_("IRQ line settings"))

        self.set_sw(IRQSettingsWidget(irq, self.mach, self))
        self.sw.grid(row = 0, column = 0, sticky = "NEWS")
