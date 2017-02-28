from .qom_settings import \
    QOMDescriptionSettingsWidget

from qemu import \
    PCIId, \
    DOp_SetPCIIdAttr, \
    POp_AddDesc, \
    DOp_SetAttr

from .gui_frame import \
    GUIFrame

from six.moves.tkinter import \
    BOTH, \
    StringVar

from .var_widgets import \
    VarLabel

from .hotkey import \
    HKEntry

from common import \
    mlget as _

from .obj_ref_var import \
    ObjRefVar

from .pci_id_widget import \
    PCIIdWidget

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

            if val_type is int:
                v = StringVar()
                w = HKEntry(f, textvariable = v)
            elif val_type is PCIId:
                """ Value of PCI Id could be presented either by PCIId object
                or by a string. So the actual widget/variable pair will be
                assigned during refresh. """
                v = None
                w = GUIFrame(f)
                w.grid()
                w.rowconfigure(0, weight = 1)
                w.columnconfigure(0, weight = 1)
            else:
                raise Exception("Not implemented value type")

            setattr(self, "var_" + field, v)
            w.grid(row = row, column = 1, sticky = "NEWS")
            setattr(self, "w_" + field, w)

            self.fields.append((field, val_type))

    def refresh_field(self, field, val_type):
        var = getattr(self, "var_" + field)
        val = getattr(self.desc, field)

        if val_type is int:
            var.set(str(val))

            e = getattr(self, "w_" + field)
            e.config(bg = "white")
        elif val_type is PCIId:
            if not PCIId.db.built and val is None:
                # use string values only without database
                val = ""
            # use appropriate widget/variable pair
            if isinstance(val, str):
                if type(var) is not StringVar:
                    var = StringVar()

                    setattr(self, "var_" + field, var)

                    frame = getattr(self, "w_" + field)

                    for w in frame.winfo_children():
                        w.destroy()

                    e = HKEntry(frame, textvariable = var)
                    e.grid(row = 0, column = 0, sticky = "NEWS")
            elif val is None or isinstance(val, PCIId):
                if type(var) is not ObjRefVar:
                    var = ObjRefVar()

                    setattr(self, "var_" + field, var)

                    frame = getattr(self, "w_" + field)

                    for w in frame.winfo_children():
                        w.destroy()

                    w = PCIIdWidget(var, frame)
                    w.grid(row = 0, column = 0, sticky = "NEWS")

            var.set(val)
        else:
            raise Exception("Not implemented value type")

    def __refresh__(self):
        QOMDescriptionSettingsWidget.__refresh__(self)

        for f in self.fields:
            self.refresh_field(*f)

    def __apply_internal__(self):
        prev_pos = self.pht.pos

        for field, val_type in self.fields:
            var = getattr(self, "var_" + field)
            new_val = var.get()

            w = getattr(self, "w_" + field)

            if val_type is int:
                try:
                    new_val = long(new_val, 0)
                except:
                    
                    w.config(bg = "red")
                    continue
                else:
                    w.config(bg = "white")
            elif val_type is PCIId:
                pass
            else:
                raise Exception("Not implemented value type")

            cur_val = getattr(self.desc, field)

            if val_type is int:
                if cur_val != new_val:
                    self.pht.stage(DOp_SetAttr,
                        field, new_val, self.desc
                    )
            elif val_type is PCIId:
                if new_val == "":
                    new_val = None

                if isinstance(new_val, str):
                    # Was type of value changed?
                    if isinstance(cur_val, str):
                        if cur_val != new_val:
                            self.pht.stage(DOp_SetAttr, field, new_val,
                                self.desc
                            )
                    else:
                        if cur_val is not None:
                            self.pht.stage(DOp_SetPCIIdAttr, field, None,
                                self.desc
                            )
                        self.pht.stage(DOp_SetAttr, field, new_val, self.desc)
                else:
                    if cur_val is None or isinstance(cur_val, PCIId):
                        if cur_val is not new_val:
                            self.pht.stage(DOp_SetPCIIdAttr, field, new_val,
                                self.desc
                            )
                    else:
                        self.pht.stage(DOp_SetAttr, field, None, self.desc)
                        if new_val is not None:
                            self.pht.stage(DOp_SetPCIIdAttr, field, new_val,
                                self.desc
                            )
            else:
                raise Exception("Not implemented value type")

        if prev_pos is not self.pht.pos:
            self.pht.set_sequence_description(
                _("Device template attributes customization.")
            )

    def __on_changed__(self, op, *args, **kw):
        if isinstance(op, POp_AddDesc):
            try:
                next(self.pht.p.find(name = self.desc.name))
            except StopIteration:
                # the operation removes current description
                return

        for field, val_type in self.fields:
            if op.writes((self.desc.name, field)):
                self.__refresh__()
                return

        QOMDescriptionSettingsWidget.__on_changed__(self, op, *args, **kw)
