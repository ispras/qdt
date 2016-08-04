from var_widgets import \
    VarToplevel, \
    VarButton

from widgets import \
    DeviceSettingsWidget

import Tkinter as tk

from common import \
    ML as _

class DeviceSettingsWindow(VarToplevel):
    def __init__(self,
            master,
            device,
            machine_history_tracker,
            *args, **kwargs
        ):
        VarToplevel.__init__(self, master, *args, **kwargs)

        self.title(_("Device settings"))

        self.grid()
        self.columnconfigure(0, weight = 1)

        self.rowconfigure(0, weight = 1)

        self.dsw = DeviceSettingsWidget(self, device, machine_history_tracker)
        self.dsw.grid(
            row = 0,
            column = 0,
            sticky = "NEWS"
        )

        self.rowconfigure(1, weight = 0)

        fr = tk.Frame(self)
        fr.grid(
            row = 1,
            column = 0,
            sticky = "NES"
        )
        fr.rowconfigure(0, weight = 1)
        fr.columnconfigure(0, weight = 1)
        fr.columnconfigure(1, weight = 1)
        fr.columnconfigure(2, weight = 1)

        VarButton(fr,
            text = _("Refresh"),
            command = self.dsw.refresh
        ).grid(
            row = 0,
            column = 0,
            sticky = "S"
        )

        VarButton(fr,
            text = _("Apply"),
            command = self.apply
        ).grid(
            row = 0,
            column = 1,
            sticky = "S"
        )

        VarButton(fr, 
            text = _("OK"),
            command = self.apply_and_quit
        ).grid(
            row = 0,
            column = 2,
            sticky = "S"
        )

    def apply(self):
        self.dsw.apply()
        self.dsw.refresh()

    def apply_and_quit(self):
        self.dsw.apply()
        self.destroy()
