from common import mlget as _

from .hotkey import HKEntry

from .var_widgets import (
    VarLabel,
    VarButton,
    VarCombobox
)
from six.moves.tkinter import (
    END,
    StringVar
)
from six.moves.tkinter_messagebox import showerror

from qemu import (
    MOp_AddBus,
    POp_AddDesc
)
from .gui_dialog import GUIDialog

msg_title = _("Description creation error")
msg_name = _("Name '%s' is incorrect or already in use.")
msg_empty_name = _("Name is empty.")

class AddDescriptionDialog(GUIDialog):
    # If project_history_tracker is None than the window works in demo mode.
    def __init__(self, project_history_tracker = None, *args, **kw):
        GUIDialog.__init__(self, *args, **kw)

        self.title(_("Description creation"))

        self.focus()

        self.grid()
        self.columnconfigure(0, weight = 0)
        self.columnconfigure(1, weight = 1)

        self.pht = project_history_tracker

        self.rowconfigure(0, weight = 0)
        l = VarLabel(self, text = _("Description name"))
        l.grid(row = 0, column = 0, sticky = "NES")

        v = self.var_name = StringVar()
        e = self.e_name = HKEntry(self, textvariable = v)
        e.grid(row = 0, column = 1, sticky = "NEWS")
        # Set input focus to description name entry initially.
        e.focus_set()

        v.trace_variable("w", self.on_var_name_write)
        if self.pht is not None:
            # do not generate name in demo mode
            v.set(self.pht.p.gen_uniq_desc_name())
            # autoselect default name to speed up its customization
            e.selection_range(0, END)

        self.rowconfigure(1, weight = 0)
        l = VarLabel(self, text = _("Description kind"))
        l.grid(row = 1, column = 0, sticky = "NES")

        v = self.var_kind = StringVar()
        cb = self.cb_kind = VarCombobox(self,
            textvariable = v,
            values = [
                _("System bus device template"),
                _("Machine draft"),
                _("PCI(E) function template")
            ],
            state = "readonly"
        )
        v.set(cb.cget("values")[0].get())
        cb.grid(row = 1, column = 1, sticky = "NEWS")

        cb.config(width = max([len(s.get()) for s in cb.cget("values")]))

        self.rowconfigure(2, weight = 0)
        b = VarButton(self, text = _("Add"), command = self.on_add)
        b.grid(row = 2, column = 0, columns = 2, sticky = "NES")

        self.bind("<Escape>", self.on_escape, "+")

        # corresponds to 'Enter' key
        self.bind("<Return>", self.on_enter, "+")

    def on_enter(self, *args):
        self.on_add()

    def on_escape(self, event):
        self.destroy()

    def on_var_name_write(self, *args):
        self.check_name()

    def check_name(self):
        n = self.var_name.get()
        if not n:
            self.e_name.config(bg = "red")
            return False
        try:
            if self.pht is None:
                # do not check unicity in demo mode
                raise StopIteration()
            next(self.pht.p.find(name = n))
        except StopIteration:
            # free name
            self.e_name.config(bg = "white")
            return True
        else:
            # name is in use
            self.e_name.config(bg = "yellow")
            return False

    def on_add(self):
        cur_name = self.var_name.get()
        if not cur_name:
            showerror(msg_title.get(), msg_empty_name.get(),
                parent = self
            )
            return
        elif not self.check_name():
            showerror(msg_title.get(), msg_name.get() % cur_name,
                parent = self
            )
            return

        if self.pht is None:
            # check name only in demo mode
            return

        """ TODO: Directory is defined by current Qemu source tree. Hence,
        version API must be use there. """

        kind = self.cb_kind.current()
        if kind == 0:
            class_name = "SysBusDeviceDescription"
            directory = ""
        elif kind == 1:
            class_name = "MachineNode"
            directory = ""
        elif kind == 2:
            class_name = "PCIExpressDeviceDescription"
            directory = "pci"

        add_op = self.pht.stage(POp_AddDesc, class_name,
            self.pht.p.next_serial_number(),
            name = cur_name,
            directory = directory
        )

        if kind == 1:
            # automatically create system bus in the machine
            self.pht.stage(MOp_AddBus, "SystemBusNode",
                0, # id for the bus
                add_op.sn # serial number of machine description
            )

        self.pht.commit(
            sequence_description = _("Add description '%s'.") % cur_name
        )

        self.destroy()
