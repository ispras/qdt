__all__ = [
    "QOMDescriptionSettingsWidget"
]

from .gui_frame import (
    GUIFrame
)
from six.moves.tkinter import (
    GROOVE,
    BOTH,
    LabelFrame,
    Checkbutton,
    BooleanVar,
    BOTH,
    StringVar
)
from .var_widgets import (
    VarLabel,
    VarButton
)
from common import (
    mlget as _
)
from .scrollframe import (
    add_scrollbars
)
from .hotkey import (
    HKEntry
)
from qemu import (
    PCIId,
    POp_AddDesc,
    DOp_SetPCIIdAttr,
    DOp_SetAttr
)
from .qdc_gui_signal_helper import (
    QDCGUISignalHelper
)
from .obj_ref_var import (
    ObjRefVar
)
from .pci_id_widget import (
    PCIIdWidget
)
from source import (
    CINT
)


class gen_readonly_widgets(HKEntry):

    def __init__(self, master, obj, attr, _input):
        v = StringVar()
        HKEntry.__init__(self, master, textvariable = v, state = "readonly")
        self._v, self._obj, self._attr = v, obj, attr

    def _refresh(self):
        self._v.set(getattr(self._obj, self._attr))

    def _changes(self):
        return []


class SimpleEditWidget: # old style class, like Tkinter classes

    def _refresh(self):
        cur_val = getattr(self._obj, self._attr)
        if not self._validate():
            self._v.set(cur_val)
        widget_val = self._cast(self._v.get())
        if widget_val != cur_val:
            self._v.set(cur_val)
        else:
            self._do_highlight()

    _cast = lambda self, x : x

    def _validate(self):
        try:
            self._cast(self._v.get())
        except ValueError:
            return False
        else:
            return True

    def _changes(self):
        if not self._validate():
            return

        new_val = self._cast(self._v.get())
        cur_val = getattr(self._obj, self._attr)

        if new_val != cur_val:
            yield DOp_SetAttr, self._attr, new_val

    _set_color = lambda self, color : self.config(bg = color)


class gen_int_widgets(HKEntry, SimpleEditWidget):

    def __init__(self, master, obj, attr, _input):
        v = StringVar()
        HKEntry.__init__(self, master, textvariable = v)
        self._v, self._obj, self._attr = v, obj, attr
        add_highlighting(obj, self, attr)

    _cast = lambda self, x : int(x, base = 0)


class gen_CINT_widgets(gen_int_widgets):

    _cast = lambda self, x : CINT(x)

    # Note that `_refresh` is not required because `StringVar` internally
    # convert `CINT` to `str` during `set`ting.


class gen_str_widgets(HKEntry, SimpleEditWidget):

    def __init__(self, master, obj, attr, _input):
        v = StringVar()
        HKEntry.__init__(self, master, textvariable = v)
        self._v, self._obj, self._attr = v, obj, attr
        add_highlighting(obj, self, attr)


class gen_bool_widgets(Checkbutton, SimpleEditWidget):

    def __init__(self, master, obj, attr, _input):
        v = BooleanVar()
        Checkbutton.__init__(self, master, variable = v)
        self._v, self._obj, self._attr = v, obj, attr
        add_highlighting(obj, self, attr)

    _set_color = lambda self, color : self.config(selectcolor = color)


class gen_PCIId_widgets(GUIFrame, QDCGUISignalHelper):

    def __init__(self, master, obj, attr, _input):
        GUIFrame.__init__(self, master)
        # Value of PCI Id could be presented either by PCIId object or by a
        # string depending on QVC availability. Hence, the actual
        # widget/variable pair will be assigned during refresh.
        self._v = None
        self._obj, self._attr = obj, attr

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)

        self.qsig_watch("qvc_available", self._refresh)

        self.bind("<Destroy>", self._on_destroy, "+")

    def _refresh(self):
        cur_val = getattr(self._obj, self._attr)
        if not PCIId.db.built and cur_val is None:
            # use string values only without database
            cur_val = ""
                # use appropriate widget/variable pair

        _v = self._v
        if isinstance(cur_val, str):
            if not isinstance(_v, StringVar):
                self._v = _v = StringVar()
                # Fill frame with appropriate widget
                for cw in self.winfo_children():
                    cw.destroy()

                cw = HKEntry(self, textvariable = _v)
                cw.grid(row = 0, column = 0, sticky = "NEWS")
        elif cur_val is None or isinstance(cur_val, PCIId):
            if not isinstance(_v, ObjRefVar):
                self._v = _v = ObjRefVar()

                for cw in self.winfo_children():
                    cw.destroy()

                cw = PCIIdWidget(_v, self)
                cw.grid(row = 0, column = 0, sticky = "NEWS")

        widget_val = _v.get()

        if widget_val != cur_val:
            _v.set(cur_val)

    def _changes(self):
        attr = self._attr
        cur_val = getattr(self._obj, attr)
        new_val = self._v.get()

        if new_val == "":
            new_val = None

        if isinstance(new_val, str): # handle new string value
            # Was type of value changed?
            if isinstance(cur_val, str):
                if new_val != cur_val:
                    yield DOp_SetAttr, attr, new_val
            else:
                """ Yes. Current value must first become the None and
                then become the new string value. """
                if cur_val is not None:
                    yield DOp_SetPCIIdAttr, attr, None
                yield DOp_SetAttr, attr, new_val
        else: # Handle new value as PCIId (None equivalent to a PCIId)
            if cur_val is None or isinstance(cur_val, PCIId):
                if cur_val is not new_val:
                    yield DOp_SetPCIIdAttr, attr, new_val
            else:
                """ Current string value must first be replaced with
                None and then set to new PCIId value. """
                yield DOp_SetAttr, attr, None
                if new_val is not None:
                    yield DOp_SetPCIIdAttr, attr, new_val

    def _on_destroy(self, *_, **__):
        self.qsig_unwatch("qvc_available", self._refresh)


def gen_widgets(master, obj, attr, _input):
    # An input descriptor may be given by an instance rather than
    # a type. The instance may contain extra information for
    # corresponding widget generator.
    if isinstance(_input, type):
        _input_name = _input.__name__
    else:
        _input_name = type(_input).__name__

    try:
        generator = globals()["gen_%s_widgets" % _input_name]
    except AttributeError:
        raise RuntimeError("Input of QOM template attribute %s of"
            " type %s is not supported" % (attr, _input_name)
        )

    return generator(master, obj, attr, _input)


class DictPairWidget(GUIFrame):

    def __init__(self, master, _dict, key, key_desc, value_desc):
        GUIFrame.__init__(self, master, borderwidth = 2, relief = GROOVE)

        self.rowconfigure(0, weight = 0)
        self.rowconfigure(1, weight = 1)
        self.columnconfigure(0, weight = 1)

        self._dict = _dict
        self._key = key

        # self is a proxy for the dict
        key_w = gen_widgets(self, self, "key", key_desc)
        key_w.grid(row = 0, column = 0, sticky = "NESW")

        value_w = gen_widgets(self, self, "value", value_desc)
        value_w.grid(row = 1, column = 0, sticky = "NESW")

        self.key_w, self.value_w = key_w, value_w

    @property
    def key(self):
        return self._key

    @property
    def value(self):
        return self._dict[self._key]

    def _refresh(self):
        self.key_w._refresh()
        self.value_w._refresh()


def gen_dict_widgets(master, obj, attr, _input):
    """
:param _input:
    A dict with only one entry: key is a descriptor of key for editor and
    value is a descriptor of value for editor.
    """

    key_input, value_input = list(_input.items())[0]

    w = GUIFrame(master)
    # w.columnconfigure(0, weight = 0)

    # widgets of editing of key-value pairs of the `dict`
    w._pair_widgets = pair_widgets = []

    def _refresh():
        val = getattr(obj, attr)

        new_keys = set([] if val is None else val.keys())
        obsolete_pair_widgets = []

        # check which keys are actually new
        for pw in pair_widgets:
            if pw._key in new_keys:
                new_keys.remove(pw._key)
            else:
                obsolete_pair_widgets.append(pw)

        # provide widgets for new keys
        for new_key in new_keys:
            # re-use obsolete widgets
            if obsolete_pair_widgets:
                pw = obsolete_pair_widgets.pop()
                pw._key = new_key
            else:
                # no obsolete widgets left, create new one
                pw = DictPairWidget(w, val, new_key, key_input, value_input)
                pw.pack(expand = True, fill = BOTH)
                pair_widgets.append(pw)

        # remove unused obsolete widgets
        for pw in obsolete_pair_widgets:
            pair_widgets.remove(pw)
            pw.destroy()

        # refreshing of keys and values
        for pw in pair_widgets:
            pw._refresh()

    w._refresh = _refresh

    # TODO
    w._changes = lambda : []

    return w


class ListItemWidget(LabelFrame):

    def __init__(self, master, _list, index, value_desc):
        LabelFrame.__init__(self, master, text = "")

        self._list = _list

        self._index = None
        self.index = index

        # self is a proxy for list
        self.w_value = value_w = gen_widgets(self, self, "value", value_desc)
        value_w.pack(expand = True, fill = BOTH)

    @property
    def index(self):
        return self._index

    @index.setter
    def index(self, value):
        if value == self._index:
            return

        self.config(text = str(value))

        self._index = value

    @property
    def value(self):
        return self._list[self._index]

    def _refresh(self):
        self.w_value._refresh()


def gen_list_widgets(master, obj, attr, _input):
    """
:param _input:
    A list with only one item: a descriptor of value for editor.
    """

    value_input = _input[0]

    w = GUIFrame(master)
    # w.columnconfigure(0, weight = 0)

    w._item_widgets = item_widgets = []

    def _refresh():
        val = getattr(obj, attr)

        if val is None:
            val = []

        # create widgets for new objects ...
        for idx in range(len(item_widgets), len(val)):
            iw = ListItemWidget(w, val, idx, value_input)
            item_widgets.append(iw)
            iw.pack(expand = True, fill = BOTH)

        # ... or remove unused widgets
        for _ in range(len(val), len(item_widgets)):
            item_widgets.pop().destroy()

        for iw in item_widgets:
            iw._refresh()

    w._refresh = _refresh

    # TODO
    w._changes = lambda : []

    return w


def add_highlighting(desc, widget, attr):
    def do_highlight(w = widget, attr = attr):
        if not w._validate():
            w._set_color("red")
        elif w._cast(widget._v.get()) != getattr(desc, attr):
            w._set_color("#ffffcc")
        else:
            w._set_color("white")

    widget._do_highlight = do_highlight

    # This code is outlined from the loop because of late binding of
    # `do_highlight` in the lambda.
    # See: https://stackoverflow.com/questions/3431676/creating-functions-in-a-loop
    widget._v.trace_variable("w", lambda *_: do_highlight())


class QOMDescriptionSettingsWidget(GUIFrame):
    def __init__(self, qom_desc, *args, **kw):
        GUIFrame.__init__(self, *args, **kw)

        # Main frame defines appearance of base widget content. Subclasses
        # may append widgets using `pack` manager but those extra widgets
        # must not affect base widgets.
        main_frame = GUIFrame(self)
        main_frame.pack(fill = BOTH, expand = False)

        main_frame.columnconfigure(0, weight = 1)
        main_frame.rowconfigure(0, weight = 1) # settings
        # buttons, must always be visible
        # XXX: Probably because of a bug, but zero weight (default) results
        # in granting all required space to corresponding row.
        main_frame.rowconfigure(1)

        self.desc = qom_desc
        try:
            self.pht = self.winfo_toplevel().pht
        except AttributeError:
            self.pht = None

        # shapshot mode without PHT
        if self.pht is not None:
            self.pht.watch_changed(self.__on_changed__)

        sf = self.settings_fr = GUIFrame(main_frame)
        sf.grid(row = 0, column = 0, sticky = "NESW")

        scrolled = add_scrollbars(sf, GUIFrame)

        f = self.qomd_fr = GUIFrame(scrolled)
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
                w = gen_readonly_widgets(f, qom_desc, attr)
            else:
                w = gen_widgets(f, qom_desc, attr, _input)

            w.grid(row = row, column = 1, sticky = "NEWS")
            setattr(self, "_w_" + attr, w)

        btf = self.buttons_fr = GUIFrame(main_frame)
        btf.grid(row = 1, column = 0, sticky = "NESW")

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

    def __on_qvc_available(self):
        self.__refresh__()

    def __refresh__(self):
        for attr in self.desc.__attribute_info__:
            getattr(self, "_w_" + attr)._refresh()

    def __apply__(self):
        if self.pht is None:
            # snapshot mode
            return

        prev_pos = self.pht.pos

        desc = self.desc
        desc_sn = desc.__sn__

        for attr in desc.__attribute_info__:
            for args in getattr(self, "_w_" + attr)._changes():
                self.pht.stage(*(args + (desc_sn,)))

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

    def __on_apply__(self):
        self.__apply__()

    def __on_refresh__(self):
        self.__refresh__()

    def set_layout(self, layout):
        pass

    def gen_layout(self):
        return {}
