from qom_settings import \
    QOMDescriptionSettingsWidget

from qemu import \
    DOp_SetAttr

from gui_frame import \
    GUIFrame

from Tkinter import \
    BOTH, \
    StringVar

from var_widgets import \
    VarLabel

from hotkey import \
    HKEntry

class DeviceDescriptionSettingsWidget(QOMDescriptionSettingsWidget):
    def __init__(self, fields_and_names, *args, **kw):
        QOMDescriptionSettingsWidget.__init__(self, *args, **kw)

        f = self.fields_fr = GUIFrame(self.settings_fr)
        f.pack(fill = BOTH, expand = False)

        f.columnconfigure(0, weight = 0)
        f.columnconfigure(1, weight = 1)

        self.fields = []

        for row, (field, text, val_type) in enumerate(fields_and_names):
            f.rowconfigure(row, weight = 0)

            l = VarLabel(f, text = text)
            l.grid(row = row, column = 0, sticky = "NES")

            v = StringVar()
            setattr(self, "var_" + field, v)

            if val_type is long:
                e = HKEntry(f, textvariable = v)
                e.grid(row = row, column = 1, sticky = "NEWS")

                setattr(self, "e_" + field, e)

            self.fields.append((field, val_type))

    def refresh_field(self, field, val_type):
        var = getattr(self, "var_" + field)
        val = getattr(self.desc, field)

        if val_type is long:
            var.set(str(val))

            e = getattr(self, "e_" + field)
            e.config(bg = "white")
        else:
            raise Exception("Not implemented value type")

    def __refresh__(self):
        QOMDescriptionSettingsWidget.__refresh__(self)

        for f in self.fields:
            self.refresh_field(*f)

    def __apply_internal__(self):
        for field, val_type in self.fields:
            var = getattr(self, "var_" + field)
            new_val = var.get()

            e = getattr(self, "e_" + field)

            if val_type is long:
                try:
                    new_val = long(new_val, 0)
                except:
                    
                    e.config(bg = "red")
                    continue
                else:
                    e.config(bg = "white")
            else:
                raise Exception("Not implemented value type")

            cur_val = getattr(self.desc, field)

            if val_type is long:
                if cur_val != new_val:
                    self.pht.stage(DOp_SetAttr,
                        field, new_val, self.desc
                    )
            else:
                raise Exception("Not implemented value type")

    def __on_changed__(self, op, *args, **kw):
        for field, val_type in self.fields:
            if op.writes((self.desc.name, field)):
                self.refresh_field(field, val_type) 
