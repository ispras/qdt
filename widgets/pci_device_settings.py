from .device_settings import DeviceSettingsWidget

from common import mlget as _

from six.moves import range as xrange

from six.moves.tkinter import (
    BOTH,
    StringVar,
    BooleanVar
)
from six import integer_types

from .var_widgets import (
    VarLabelFrame,
    VarLabel,
    VarCheckbutton
)
import sys

from .hotkey import HKEntry

class PCIDeviceSettingsWidget(DeviceSettingsWidget):
    def __init__(self, *args, **kw):
        DeviceSettingsWidget.__init__(self, *args, **kw)

        lf = VarLabelFrame(self, text = _("PCI"))
        lf.pack(fill = BOTH, expand = False)

        lf.columnconfigure(0, weight = 0)
        lf.columnconfigure(1, weight = 1)
        for row in xrange(0, 3):
            lf.rowconfigure(row, weight = 1)

        l = VarLabel(lf, text = _("Slot (Device number)"))
        l.grid(row = 0, column = 0, sticky = "NES")

        self.var_slot = StringVar()
        e = HKEntry(lf, textvariable = self.var_slot)
        e.grid(row = 0, column = 1, sticky = "NEWS")

        l = VarLabel(lf, text = _("Function number"))
        l.grid(row = 1, column = 0, sticky = "NES")

        self.var_function = StringVar()
        e = HKEntry(lf, textvariable = self.var_function)
        e.grid(row = 1, column = 1, sticky = "NEWS")

        self.var_multifunction = BooleanVar()
        chb = VarCheckbutton(lf,
            variable = self.var_multifunction,
            text = _("multifunction")
        )
        chb.grid(row = 2, column = 0, columnspan = 2, sticky = "NWS")

    def refresh(self):
        DeviceSettingsWidget.refresh(self)

        self.var_slot.set(self.dev.slot)
        self.var_function.set(self.dev.function)
        self.var_multifunction.set(self.dev.multifunction)

    def __apply_internal__(self):
        DeviceSettingsWidget.__apply_internal__(self)

        for attr in [ "slot", "function", "multifunction" ]:
            new_val = getattr(self, "var_" + attr).get()
            cur_val = getattr(self.dev, attr)

            if isinstance(cur_val, bool):
                pass
            elif isinstance(cur_val, integer_types):
                try:
                    new_val = int(new_val, base = 0)
                except ValueError:
                    pass

            if new_val == cur_val:
                continue

            self.mht.stage(
                getattr(sys.modules["qemu"], "MOp_PCIDevSet" + attr.title()),
                new_val,
                self.dev.id
            )

        self.mht.set_sequence_description(_("PCI device configuration."))
