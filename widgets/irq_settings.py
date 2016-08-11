from settings_window import \
    SettingsWidget, \
    SettingsWindow

from common import \
    ML as _

from var_widgets import \
    VarLabelFrame, \
    VarLabel

from qemu import \
    MachineNodeOperation, \
    DeviceNode, \
    IRQLine, \
    IRQHub

from Tkinter import \
    Entry, \
    StringVar

from ttk import \
    Combobox

from device_settings import \
    DeviceSettingsWidget

class IRQSettingsWidget(SettingsWidget):
    def __init__(self, irq, *args, **kw):
        SettingsWidget.__init__(self, *args, **kw)

        self.irq = irq

        self.columnconfigure(0, weight = 1)

        for lf_row, (pfx, txt) in enumerate([
            ("src_", _("Source")),
            ("dst_", _("Destination"))
        ]):
            self.rowconfigure(lf_row, weight = 0)

            lf = VarLabelFrame(self, text = txt)
            lf.grid(row = lf_row, column = 0, sticky = "NEW")

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

            index_l = VarLabel(lf, text = _("GPIO index"))
            index_l.grid(row = 1, column = 0, sticky = "NE")

            index_var = StringVar()
            index_e = Entry(lf, textvariable = index_var)
            index_e.grid(row = 1, column = 1, sticky = "NEW")

            name_l = VarLabel(lf, text = _("GPIO name"))
            name_l.grid(row = 2, column = 0, sticky = "NE")

            name_var = StringVar()
            name_e = Entry(lf, textvariable = name_var)
            name_e.grid(row = 2, column = 1, sticky = "NEW")

            for v in ["lf", "node_var", "node_cb",
                      "index_l", "index_e", "index_var", 
                      "name_l", "name_e", "name_var"]:
                setattr(self, pfx + v, locals()[v])

    def on_node_text_changed(self, *args):
        for pfx in [ "src", "dst" ]:
            node_var = getattr(self, pfx + "_node_var")
            node_text = node_var.get()

            if not node_text:
                continue

            node = self.find_node_by_link_text(node_text)

            index_l = getattr(self, pfx + "_index_l")
            index_e = getattr(self, pfx + "_index_e")
            name_l = getattr(self, pfx + "_name_l")
            name_e = getattr(self, pfx + "_name_e")

            dev_widgets = [index_l, index_e, name_l, name_e]

            if isinstance(node, DeviceNode):
                for w in dev_widgets:
                    w.config(state = "normal")
            else:
                for w in dev_widgets:
                    w.config(state = "disabled")

    def __apply_internal__(self):
        pass

    def refresh(self):
        nodes = [ DeviceSettingsWidget.gen_node_link_text(node) \
            for node in self.mht.mach.devices + self.mht.mach.irq_hubs ]

        for pfx in [ "src", "dst" ]:
            cb = getattr(self, pfx + "_node_cb")
            cb.config(values = nodes)

            # IRQ line end (source or destination)
            end_widget = getattr(self.irq, pfx)
            end_node = end_widget.node
            node_text = DeviceSettingsWidget.gen_node_link_text(end_node)
            node_var = getattr(self, pfx + "_node_var")
            node_var.set(node_text)

            if isinstance(end_node, DeviceNode):
                index_var = getattr(self, pfx + "_index_var")
                name_var = getattr(self, pfx + "_name_var")

                # IRQ descriptor in machine description
                irq_node = self.irq.node
                if isinstance(irq_node, IRQLine): 
                    end_desc = getattr(self.irq.node, pfx)
                elif isinstance(irq_node, IRQHub):
                    # search the end in hub end list
                    for end_desc in getattr(irq_node, pfx + "s"):
                        if end_desc[0] == end_node:
                            break

                index_var.set(str(end_desc[1]))

                if end_desc[2] is not None:
                    name_var.set(str(end_desc[2]))
                else:
                    name_var.set("")

    def on_changed(self, op, *args, **kw):
        if not isinstance(op, MachineNodeOperation):
            return

        if not op.writes_node():
            return

        self.refresh()

class IRQSettingsWindow(SettingsWindow):
    def __init__(self, *args, **kw):
        irq = kw.pop("irq")

        SettingsWindow.__init__(self, *args, **kw)

        self.title(_("IRQ line settings"))

        self.sw = IRQSettingsWidget(irq, self.mht, self)
        self.sw.grid(row = 0, column = 0, sticky = "NEWS")
