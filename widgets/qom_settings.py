from .gui_frame import \
    GUIFrame

from six.moves.tkinter import \
    BOTH, \
    StringVar

from .var_widgets import \
    VarLabel, \
    VarButton

from common import \
    mlget as _

from .hotkey import \
    HKEntry

from qemu import \
    POp_AddDesc, \
    DOp_SetAttr

from .qdc_gui_signal_helper import \
    QDCGUISignalHelper

def validate_int(var, entry):
    try:
        (int(var.get(), base = 0))
    except ValueError:
        entry.config(bg = "red")
    else:
        entry.config(bg = "white")

class QOMDescriptionSettingsWidget(GUIFrame, QDCGUISignalHelper):
    def __init__(self, qom_desc, *args, **kw):
        GUIFrame.__init__(self, *args, **kw)

        self.desc = qom_desc
        try:
            self.pht = self.winfo_toplevel().pht
        except AttributeError:
            self.pht = None

        # shapshot mode without PHT
        if self.pht is not None:
            self.pht.add_on_changed(self.__on_changed__)

        sf = self.settings_fr = GUIFrame(self)
        sf.pack(fill = BOTH, expand = False)

        f = self.qomd_fr = GUIFrame(sf)
        f.pack(fill = BOTH, expand = False)

        f.columnconfigure(0, weight = 0)
        f.columnconfigure(1, weight = 1)

        for row, (attr, info) in enumerate(qom_desc.__attribute_info__.items()):
            f.rowconfigure(row, weight = 0)

            l = VarLabel(f, text = info["short"])
            l.grid(row = row, column = 0, sticky = "NES")

            try:
                _input = info["input"]
            except KeyError:
                # attribute is read-only
                v = StringVar()
                w = HKEntry(f, textvariable = v, state="readonly")
            else:
                if _input is str:
                    v = StringVar()
                    w = HKEntry(f, textvariable = v)
                elif _input is int:
                    v = StringVar()
                    w = HKEntry(f, textvariable = v)

                    def validate(varname, junk, act, entry = w, var = v):
                        validate_int(var, entry = entry)

                    v.trace_variable("w", validate)
                else:
                    raise RuntimeError("Input of QOM template attribute %s of"
                        " type %s is not supported" % (attr, _input.__name__)
                    )

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

        self.bind("<Destroy>", self.__on_destory__, "+")

    def __refresh__(self):
        desc = self.desc
        for attr in desc.__attribute_info__:
            v = getattr(self, "_var_" + attr)
            cur_val = getattr(desc, attr)
            # TODO: check already equal
            v.set(cur_val)

    def __apply__(self):
        if self.pht is None:
            # snapshot mode
            return

        prev_pos = self.pht.pos

        desc = self.desc
        for attr, info in desc.__attribute_info__.items():
            try:
                _input = info["input"]
            except KeyError: # read-only
                continue

            v = getattr(self, "_var_" + attr)
            cur_val = getattr(desc, attr)
            new_val = v.get()

            if _input is int:
                try:
                    new_val = int(new_val, base = 0)
                except ValueError:
                    # bad value cannot be applied
                    continue

            if new_val != cur_val:
                self.pht.stage(DOp_SetAttr, attr, new_val, desc)

        if prev_pos is not self.pht.pos:
            self.pht.set_sequence_description(_("QOM object configuration."))

        self.__apply_internal__()

        self.pht.commit()

    def __on_changed__(self, op, *args, **kw):
        if not op.writes(self.desc.name):
            return
 
        if isinstance(op, POp_AddDesc):
            try:
                next(self.pht.p.find(name = self.desc.name))
            except StopIteration:
                # the operation removes current description
                return

        self.__refresh__()

    def __on_destory__(self, *args, **kw):
        if self.pht is not None:
            self.pht.remove_on_changed(self.__on_changed__)

    def __on_apply__(self):
        self.__apply__()

    def __on_refresh__(self):
        self.__refresh__()

    def set_layout(self, layout):
        pass

    def gen_layout(self):
        return {}
