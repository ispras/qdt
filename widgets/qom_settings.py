__all__ = [
    "QOMDescriptionSettingsWidget"
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
from .obj_ref_var import (
    ObjRefVar,
)
from .pci_id_widget import (
    PCIIdWidget,
)
from .qdc_gui_signal_helper import (
    QDCGUISignalHelper,
)
from qemu import (
    DOp_SetAttr,
    DOp_SetPCIIdAttr,
    PCIId,
    POp_AddDesc,
)
from .var_widgets import (
    VarButton,
    VarLabel,
)

from six.moves.tkinter import (
    BooleanVar,
    BOTH,
    Checkbutton,
    StringVar,
)


class QOMDescriptionSettingsWidget(GUIFrame, QDCGUISignalHelper):

    def __init__(self, *args, **kw):
        self.desc = qom_desc = kw.pop("qom_desc")
        GUIFrame.__init__(self, *args, **kw)

        try:
            self.pht = self.winfo_toplevel().pht
        except AttributeError:
            self.pht = None

        # shapshot mode without PHT
        if self.pht is not None:
            self.pht.watch_changed(self.__on_changed__)

        sf = self.settings_fr = GUIFrame(self)
        sf.pack(fill = BOTH, expand = False)

        f = self.qomd_fr = GUIFrame(sf)
        f.pack(fill = BOTH, expand = False)

        f.columnconfigure(0, weight = 0)
        f.columnconfigure(1, weight = 1)

        have_pciid = False
        self._all_highlights = []

        for row, (attr, info) in enumerate(qom_desc.__attribute_info__.items()):
            f.rowconfigure(row, weight = 0)

            l = VarLabel(f, text = info["short"])
            l.grid(row = row, column = 0, sticky = "NES")

            try:
                _input = info["input"]
            except KeyError:
                # attribute is read-only
                v = StringVar()
                w = HKEntry(f, textvariable = v, state = "readonly")
            else:
                if _input is PCIId:
                    have_pciid = True

                _input_name = _input.__name__

                try:
                    generator = getattr(self, "gen_%s_widgets" % _input_name)
                except AttributeError:
                    raise RuntimeError("Input of QOM template attribute %s of"
                        " type %s is not supported" % (attr, _input_name)
                    )

                v, w = generator(f)

                if v is not None:
                    self._add_highlighting(v, w, attr)

            w.grid(row = row, column = 1, sticky = "NEWS")
            setattr(self, "_var_" + attr, v)
            setattr(self, "_w_" + attr, w)

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

        self.bind("<Destroy>", self.__on_destroy__, "+")

        self.__have_pciid = have_pciid
        if have_pciid:
            self.qsig_watch("qvc_available", self.__on_qvc_available)

    def _add_highlighting(self, var, widget, attr):
        def do_highlight(w = widget, v = var, attr = attr):
            if not w._validate():
                w._set_color("red")
            elif w._cast(v.get()) != getattr(self.desc, attr):
                w._set_color("#ffffcc")
            else:
                w._set_color("white")

        self._all_highlights.append(do_highlight)

        # This code is outlined from the loop because of late binding of
        # `do_highlight` in the lambda.
        # See: https://stackoverflow.com/questions/3431676/creating-functions-in-a-loop
        var.trace_variable("w", lambda *_: do_highlight())

    def gen_int_widgets(self, master):
        v = StringVar()
        w = HKEntry(master, textvariable = v)

        def validate():
            try:
                (int(v.get(), base = 0))
            except ValueError:
                return False
            else:
                return True

        w._validate = validate
        w._set_color = lambda color : w.config(bg = color)
        w._cast = lambda x : int(x, base = 0)
        return v, w

    def gen_str_widgets(self, master):
        v = StringVar()
        w = HKEntry(master, textvariable = v)
        w._validate = lambda : True
        w._set_color = lambda color : w.config(bg = color)
        w._cast = lambda x : x
        return v, w

    def gen_bool_widgets(self, master):
        v = BooleanVar()
        w = Checkbutton(master, variable = v)
        w._validate = lambda : True
        w._set_color = lambda color : w.config(selectcolor = color)
        w._cast = lambda x : x
        return v, w

    def gen_PCIId_widgets(self, master):
        # Value of PCI Id could be presented either by PCIId object or by a
        # string depending on QVC availability. Hence, the actual
        # widget/variable pair will be assigned during refresh.
        v = None
        w = GUIFrame(master)
        w.grid()
        w.rowconfigure(0, weight = 1)
        w.columnconfigure(0, weight = 1)
        return v, w

    def __on_qvc_available(self):
        self.__refresh__()

    def __refresh__(self):
        desc = self.desc
        for attr, info in desc.__attribute_info__.items():
            try:
                _input = info["input"]
            except KeyError:
                _input = None

            cur_val = getattr(desc, attr)
            v = getattr(self, "_var_" + attr)

            if _input is PCIId:
                if not PCIId.db.built and cur_val is None:
                    # use string values only without database
                    cur_val = ""
                # use appropriate widget/variable pair
                if isinstance(cur_val, str):
                    if not isinstance(v, StringVar):
                        v = StringVar()
                        setattr(self, "_var_" + attr, v)

                        # Fill frame with appropriate widget
                        frame = getattr(self, "_w_" + attr)
                        for w in frame.winfo_children():
                            w.destroy()

                        w = HKEntry(frame, textvariable = v)
                        w.grid(row = 0, column = 0, sticky = "NEWS")
                elif cur_val is None or isinstance(cur_val, PCIId):
                    if not isinstance(v, ObjRefVar):
                        v = ObjRefVar()
                        setattr(self, "_var_" + attr, v)

                        frame = getattr(self, "_w_" + attr)

                        for w in frame.winfo_children():
                            w.destroy()

                        w = PCIIdWidget(v, frame)
                        w.grid(row = 0, column = 0, sticky = "NEWS")

            widget_val = v.get()

            if _input is int:
                try:
                    widget_val = int(widget_val, base = 0)
                except ValueError:
                    widget_val = None

            if widget_val != cur_val:
                v.set(cur_val)

        for cb in self._all_highlights:
            cb()

    def __apply__(self):
        if self.pht is None:
            # snapshot mode
            return

        prev_pos = self.pht.pos

        desc = self.desc
        desc_sn = desc.__sn__

        for attr, info in desc.__attribute_info__.items():
            try:
                _input = info["input"]
            except KeyError: # read-only
                continue

            v = getattr(self, "_var_" + attr)
            cur_val = getattr(desc, attr)
            new_val = v.get()

            if _input is PCIId:
                if new_val == "":
                    new_val = None

                if isinstance(new_val, str): # handle new string value
                    # Was type of value changed?
                    if isinstance(cur_val, str):
                        if new_val != cur_val:
                            self.pht.stage(DOp_SetAttr, attr, new_val, desc_sn)
                    else:
                        """ Yes. Current value must first become the None and
                        then become the new string value. """
                        if cur_val is not None:
                            self.pht.stage(DOp_SetPCIIdAttr, attr, None,
                                desc_sn
                            )
                        self.pht.stage(DOp_SetAttr, attr, new_val, desc_sn)
                else: # Handle new value as PCIId (None equivalent to a PCIId)
                    if cur_val is None or isinstance(cur_val, PCIId):
                        if cur_val is not new_val:
                            self.pht.stage(DOp_SetPCIIdAttr, attr, new_val,
                                desc_sn
                            )
                    else:
                        """ Current string value must first be replaced with
                        None and then set to new PCIId value. """
                        self.pht.stage(DOp_SetAttr, attr, None, desc_sn)
                        if new_val is not None:
                            self.pht.stage(DOp_SetPCIIdAttr, attr, new_val,
                                desc_sn
                            )
            else:
                if _input is int:
                    try:
                        new_val = int(new_val, base = 0)
                    except ValueError: # bad value cannot be applied
                        continue

                if new_val != cur_val:
                    self.pht.stage(DOp_SetAttr, attr, new_val, desc_sn)

        if prev_pos is not self.pht.pos:
            self.pht.set_sequence_description(_("QOM object configuration."))

        try:
            apply_internal = self.__apply_internal__
        except AttributeError: # apply logic extension is optional
            pass
        else:
            apply_internal()

        self.pht.commit()

    def __on_changed__(self, op, *args, **kw):
        if isinstance(op, POp_AddDesc):
            if not hasattr(self.desc, "__sn__"):
                # the operation removes current description
                return

        if not op.writes(self.desc.__sn__):
            return

        self.__refresh__()

    def __on_destroy__(self, *args, **kw):
        if self.pht is not None:
            self.pht.unwatch_changed(self.__on_changed__)

        if self.__have_pciid:
            self.qsig_unwatch("qvc_available", self.__on_qvc_available)

    def __on_apply__(self):
        self.__apply__()

    def __on_refresh__(self):
        self.__refresh__()

    def set_layout(self, layout):
        pass

    def gen_layout(self):
        return {}
