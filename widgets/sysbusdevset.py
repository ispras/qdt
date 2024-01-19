__all__ = [
    "SystemBusDeviceSettingsWidget"
]

from common import (
    mlget as _,
)
from .device_settings import (
    DeviceSettingsWidget,
)
from .gui_frame import (
    GUIFrame,
)
from .hotkey import (
    HKEntry,
)
from qemu import (
    MOp_AddIOMapping,
    MOp_DelIOMapping,
    MOp_SetIOMapping,
)
from .var_widgets import (
    VarButton,
    VarLabelFrame,
)

from six import (
    integer_types,
)
from six.moves import (
    range as xrange,
)
from six.moves.tkinter import (
    BOTH,
    Label,
    StringVar,
)


def gen_mapping_string(mapping):
    if mapping is None:
        return ""
    elif isinstance(mapping, integer_types):
        return "0x%0x" % mapping
    else:
        return str(mapping)

def parse_mapping_string(mapping):
    if not mapping:
        return None
    try:
        val = int(mapping, base = 0)
    except ValueError:
        val = str(mapping)
    return val

class SystemBusDeviceSettingsWidget(DeviceSettingsWidget):
    def __init__(self, *args, **kw):
        DeviceSettingsWidget.__init__(self, *args, **kw)

        for __, mio in enumerate([
                ("mmio", _("MMIO Mappings")), 
                ("pmio", _("PMIO Mappings")) ], 2):
            lf = VarLabelFrame(
                self, text = mio[1]
            )
            lf.pack(fill = BOTH, expand = False)
            lf.columnconfigure(0, weight = 1)

            fr = GUIFrame(lf)
            fr.grid(row = 0, column = 0, sticky = "NEWS")
            lf.rowconfigure(0, weight = 1)
            fr.columnconfigure(0, weight = 0)
            fr.columnconfigure(1, weight = 1)

            bt_fr = GUIFrame(lf)
            bt_fr.grid(row = 1, column = 0, sticky = "NEWS")
            lf.rowconfigure(1, weight = 0)

            bt_add = VarButton(bt_fr,
                text = _("Add"),
                command = getattr(self, "on_add_" + mio[0])
            )
            bt_add.grid(row = 0, column = 0, sticky = "NES")

            bt_del = VarButton(bt_fr,
                text = _("Delete"),
                command = getattr(self, "on_del_" + mio[0])
            )
            bt_del.grid(row = 0, column = 1, sticky = "NES")
            bt_del.config(state = "disabled")

            setattr(self, mio[0] + "_fr", fr)
            setattr(self, "bt_del_" + mio[0], bt_del)
            setattr(self, mio[0] + "_rows", [])

    def append_row_to_grid(self, grid, rows, mio):
        # update delete button
        if not rows:
            bt_del = getattr(self, "bt_del_" + mio)
            bt_del.config(state = "normal")

        row = len(rows)

        l = Label(grid, text = str(row) + ":")
        l.grid(row = row, column = 0, sticky = "NES")

        v = StringVar()
        e = HKEntry(grid, textvariable = v)
        e.grid(row = row, column = 1, sticky = "NEWS")

        row_desc = (l, e, v)

        rows.append(row_desc)

        return row_desc

    def remove_row_from_grid(self, grid, rows, mio):
        for widget in rows.pop()[:2]:
            widget.destroy()

        # update delete button
        if not rows:
            bt_del = getattr(self, "bt_del_" + mio)
            bt_del.config(state = "disabled")

    def refresh(self):
        DeviceSettingsWidget.refresh(self)

        for mio in [ "mmio", "pmio" ]:
            rows = getattr(self, mio + "_rows")
            fr = getattr(self, mio + "_fr")

            mappings = getattr(self.dev, mio + "_mappings")

            row_count = len(rows)
            mapping_count = len(mappings)
            if row_count > mapping_count:
                for __ in xrange(row_count - 1, mapping_count - 1, -1):
                    self.remove_row_from_grid(fr, rows, mio)
            elif row_count < mapping_count:
                for row in xrange(row_count, mapping_count):
                    self.append_row_to_grid(fr, rows, mio)

            for row, mapping in mappings.items():
                rows[row][2].set(
                    gen_mapping_string(mapping)
                )

    def on_add(self, mio):
        rows = getattr(self, mio + "_rows")
        fr = getattr(self, mio + "_fr")

        row = self.append_row_to_grid(fr, rows, mio)

        # TODO: a configurable default value?
        row[2].set("0x0")

    def on_del(self, mio):
        rows = getattr(self, mio + "_rows")
        fr = getattr(self, mio + "_fr")

        self.remove_row_from_grid(fr, rows, mio)

    def __apply_internal__(self):
        DeviceSettingsWidget.__apply_internal__(self)

        for mio in [ "mmio", "pmio" ]:
            rows = getattr(self, mio + "_rows")
            mappings = getattr(self.dev, mio + "_mappings")

            for idx, mapping in mappings.items():
                try:
                    row = rows[idx]
                except IndexError:
                    self.mht.stage(MOp_DelIOMapping, mio, idx, self.dev.id)
                    continue

                new_mapping_str = row[2].get()
                new_mapping = parse_mapping_string(new_mapping_str)

                if not new_mapping == mapping:
                    self.mht.stage(
                        MOp_SetIOMapping, new_mapping, mio, idx,
                        self.dev.id
                    )

            for idx, row in enumerate(rows):
                if idx in mappings:
                    continue

                new_mapping_str = row[2].get()
                new_mapping = parse_mapping_string(new_mapping_str)

                self.mht.stage(MOp_AddIOMapping, new_mapping, mio, idx, 
                    self.dev.id
                )

        self.mht.set_sequence_description(_("System bus device configuration."))

    def on_del_mmio(self):
        self.on_del("mmio")

    def on_add_mmio(self):
        self.on_add("mmio")

    def on_del_pmio(self):
        self.on_del("pmio")

    def on_add_pmio(self):
        self.on_add("pmio")
