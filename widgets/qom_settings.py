from gui_frame import \
    GUIFrame

from Tkinter import \
    BOTH, \
    StringVar

from var_widgets import \
    VarLabel, \
    VarButton

from common import \
    mlget as _

from hotkey import \
    HKEntry

from qemu import \
    POp_AddDesc, \
    DOp_SetAttr

class QOMDescriptionSettingsWidget(GUIFrame):
    def __init__(self, qom_desc, project_history_tracker, *args, **kw):
        GUIFrame.__init__(self, *args, **kw)

        self.desc = qom_desc
        self.pht = project_history_tracker

        sf = self.settings_fr = GUIFrame(self)
        sf.pack(fill = BOTH, expand = False)

        f = self.qomd_fr = GUIFrame(sf)
        f.pack(fill = BOTH, expand = False)

        f.columnconfigure(0, weight = 0)
        f.columnconfigure(1, weight = 1)

        f.rowconfigure(0, weight = 0)

        l = VarLabel(f, text = _("Name"))
        l.grid(row = 0, column = 0, sticky = "NES")

        v = self.var_name = StringVar()
        e = HKEntry(f, textvariable = v, state="readonly")
        e.grid(row = 0, column = 1, sticky = "NEWS")

        # Directory editing row
        f.rowconfigure(0, weight = 0)

        l = VarLabel(f, text = _("Directory"))
        l.grid(row = 1, column = 0, sticky = "NES")

        v = self.var_directory = StringVar()
        e = HKEntry(f, textvariable = v)
        e.grid(row = 1, column = 1, sticky = "NEWS")

        btf = self.buttons_fr = GUIFrame(self)
        btf.pack(fill = BOTH, expand = False)

        btf.rowconfigure(0, weight = 0)
        btf.columnconfigure(0, weight = 1)
        btf.columnconfigure(1, weight = 0)

        bt_apply = VarButton(btf,
            text = _("Apply"),
            command = self.__on_apply__
        )
        bt_apply.grid(row = 0, column = 1, sticky = "NEWS")

        bt_revert = VarButton(btf,
            text = _("Refresh"),
            command = self.__on_refresh__
        )
        bt_revert.grid(row = 0, column = 0, sticky = "NES")

        self.after(0, self.__refresh__)

        self.pht.add_on_changed(self.__on_changed__)

        self.bind("<Destroy>", self.__on_destory__, "+")

    def __refresh__(self):
        self.var_name.set(self.desc.name)
        self.var_directory.set(self.desc.directory)

    def __apply__(self):
        prev_pos = self.pht.pos

        new_dir = self.var_directory.get()

        if new_dir != self.desc.directory:
            self.pht.stage(DOp_SetAttr, "directory", new_dir, self.desc) 

        if prev_pos is not self.pht.pos:
            self.pht.set_sequence_description(_("QOM object configuration."))

        self.__apply_internal__()

        self.pht.commit()

    def __on_changed__(self, op, *args, **kw):
        if not op.writes(self.desc.name):
            return
 
        if isinstance(op, POp_AddDesc):
            try:
                self.pht.p.find(name = self.desc.name).next()
            except StopIteration:
                # the operation removes current description
                return

        self.__refresh__()

    def __on_destory__(self, *args, **kw):
        self.pht.remove_on_changed(self.__on_changed__)

    def __on_apply__(self):
        self.__apply__()

    def __on_refresh__(self):
        self.__refresh__()

    def set_layout(self, layout):
        pass

    def gen_layout(self):
        return {}
