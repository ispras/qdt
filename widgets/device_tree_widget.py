__all__ = [
    "QOMTreeWidget"
  , "QOMTypeSelectDialog"
  , "QOMTreeWindow"
]

from .var_widgets import (
    VarTreeview,
    VarButton,
    VarLabelFrame
)
from six.moves.tkinter import (
    BOTH,
    LEFT,
    RIGHT,
    NORMAL,
    DISABLED,
    Frame,
    Radiobutton,
    Checkbutton,
    StringVar,
    IntVar
)
from common import (
    mlget as _
)
from .gui_dialog import (
    GUIDialog
)
from .gui_toplevel import (
    GUIToplevel,
)
from .scrollframe import (
    add_scrollbars_native,
    add_scrollbars_with_tags
)
from .gui_frame import (
    GUIFrame
)
from collections import (
    namedtuple
)


class QOMTypeSelectDialog(GUIDialog):

    def __init__(self, master, *a, **kw):
        qom_tree = kw.pop("qom_tree")

        GUIDialog.__init__(self, master, *a, **kw)

        self.title(_("Device Tree"))

        self.w_qtree = w_qtree = QOMTreeWidget(self, qom_tree = qom_tree)
        w_qtree.pack(fill = BOTH, expand = True, side = LEFT)
        w_qtree.bind("<<QOMTypeSelected>>", self._on_qom_type_selected)

        fr_select = Frame(self)
        fr_select.pack(fill = BOTH, side = RIGHT)

        fr_select.columnconfigure(0, minsize = 200)
        fr_select.rowconfigure(0, weight = 1)
        fr_select.rowconfigure(1, weight = 0)

        self.fr_qt = VarLabelFrame(fr_select, text = _("Select QOM type"))
        self.fr_qt.grid(row = 0, column = 0, sticky = "NESW")

        self.bt_select = VarButton(
            fr_select,
            text = _("Select"),
            command = self._on_bt_select
        )
        self.bt_select.grid(row = 1, column = 0, sticky = "NES")
        self.bt_select.config(state = DISABLED)

        self.v_sel_type = v_sel_type = StringVar(self)
        v_sel_type.trace("w", self._on_v_sel_type_w)

        geom = "+" + str(int(master.winfo_rootx())) \
             + "+" + str(int(master.winfo_rooty()))
        self.geometry(geom)

        self.focus()

    def _on_bt_select(self):
        self._result = self.v_sel_type.get()
        self.destroy()

    def _on_v_sel_type_w(self, *__):
        v_sel_type = self.v_sel_type
        if v_sel_type.get():
            self.bt_select.config(state = NORMAL)
        else:
            self.bt_select.config(state = DISABLED)

    def _on_qom_type_selected(self, __):
        qom_type = self.w_qtree.selected
        v_sel_type = self.v_sel_type

        for widget in self.fr_qt.winfo_children():
            widget.destroy()

        if qom_type is None:
            v_sel_type.set("")
            return

        name = qom_type.name

        # Note, value of `v_sel_type` will be assigned automatically by
        # `Radiobutton`s `select` below.

        b = Radiobutton(self.fr_qt,
            text = name,
            variable = v_sel_type,
            value = name # for variable
        )
        b.pack(anchor = "w")

        for m in qom_type.macros:
            b = Radiobutton(
                self.fr_qt,
                text = m,
                variable = v_sel_type,
                value = m
            )
            b.pack(anchor = "w")

        b.select()


class QOMTreeWindow(GUIToplevel):

    def __init__(self, master, *a, **kw):
        qom_tree = kw.pop("qom_tree")

        GUIToplevel.__init__(self, master, *a, **kw)

        self.title(_("QOM Tree"))

        w_qtree = QOMTreeWidget(self, qom_tree = qom_tree)
        w_qtree.pack(fill = BOTH, expand = True)


ItemDesc = namedtuple(
    "ItemDesc",
    "parent index tags qt"
)


class QOMTreeWidget(GUIFrame):

    def __init__(self, root, *args, **kw):
        self.qom_tree = qom_tree = kw.pop("qom_tree")

        GUIFrame.__init__(self, master = root, *args, **kw)

        self.columnconfigure(0, weight = 1, minsize = 300)
        self.columnconfigure(2, weight = 1, minsize = 100)
        self.rowconfigure(0, weight = 1)

        self.device_tree = dt = VarTreeview(self, selectmode = "browse")
        dt["columns"] = "Macros"

        dt.heading("#0", text = _("Devices"))
        dt.heading("Macros", text = _("Macros"))

        dt.bind("<<TreeviewSelect>>", self._on_device_tv_select, "+")

        dt.grid(
            row = 0,
            column = 0,
            sticky = "NEWS"
        )

        add_scrollbars_native(self, dt)

        fr_at = VarLabelFrame(self, text = _("Architecture filter"))
        fr_at.grid(row = 0, rowspan = 2, column = 2, sticky = "SEWN")

        arch_buttons = Frame(fr_at, borderwidth = 0)
        arch_buttons.pack(fill = "x")

        arch_buttons.columnconfigure(0, weight = 1, minsize = 60)
        arch_buttons.columnconfigure(1, weight = 1, minsize = 60)
        arch_buttons.columnconfigure(2, weight = 1, minsize = 60)

        bt_all_arches = VarButton(arch_buttons,
            text = _("All"),
            command = self.select_arches
        )
        bt_all_arches.grid(row = 0, column = 0, sticky = "EW")

        bt_none_arches = VarButton(arch_buttons,
            text = _("None"),
            command = self.deselect_arches
        )
        bt_none_arches.grid(row = 0, column = 1, sticky = "EW")

        bt_invert_arches = VarButton(arch_buttons,
            text = _("Invert"),
            command = self.invert_arches
        )
        bt_invert_arches.grid(row = 0, column = 2, sticky = "EW")

        if not qom_tree.arches:
            bt_all_arches.config(state = "disabled")
            bt_none_arches.config(state = "disabled")
            bt_invert_arches.config(state = "disabled")

        arch_selector_outer = Frame(fr_at, borderwidth = 0)
        arch_selector_outer.pack(fill = "both", anchor = "w")
        arch_selector, scrolltag = add_scrollbars_with_tags(
            arch_selector_outer, GUIFrame
        )

        ac = self.arches_checkbox = []
        for a in sorted(list(qom_tree.arches)):
            v = IntVar()
            c = Checkbutton(arch_selector,
                text = a,
                variable = v,
                command = lambda arch = a, var = v: \
                    self.on_toggle_arch(arch, var)
            )

            c.pack(expand = 1, anchor = "w")
            c.bindtags((scrolltag,) + c.bindtags())
            c.select()
            ac.append(c)

        # key: item
        # value: ItemDesc
        self.detached_items = {}
        self.all_items = {}

        self.disabled_arches = set()

        self.selected = None

        self.qom_create_tree("", qom_tree.children)

    def select_arches(self):
        all_items = self.all_items
        dt = self.device_tree
        for i, v in self.detached_items.items():
            parent = v.parent
            ci = 0
            for c in dt.get_children(parent):
                # child index > cur index
                if all_items[c].index > v.index:
                    break
                ci += 1

            dt.move(i, parent, ci)

        self.detached_items = {}
        self.disabled_arches = set()

        for c in self.arches_checkbox:
            c.select()

        self._update_selection()

    def deselect_arches(self):
        dt = self.device_tree

        to_detach = []
        for i in self.all_items:
            if i not in self.detached_items:
                to_detach.append(i)
                self.detached_items[i] = self.all_items[i]

        dt.detach(*to_detach)
        self.disabled_arches = set(self.qom_tree.arches)

        for c in self.arches_checkbox:
            c.deselect()

        self._update_selection()

    def invert_arches(self):
        for c in self.arches_checkbox:
            c.invoke()

    def qom_create_tree(self, parent_id, qt_children):
        dt = self.device_tree
        all_items = self.all_items

        for i, key in enumerate(sorted(qt_children.keys())):
            qt = qt_children[key]
            if qt.macros:
                value = ", ".join(qt.macros)
            else:
                value = "None"

            cur_id = dt.insert(parent_id, "end",
                text = qt.name,
                values = (value, ),
                tags = list(qt.arches)
            )

            all_items[cur_id] = ItemDesc(parent_id, i, set(qt.arches), qt)

            if qt.children:
                self.qom_create_tree(cur_id, qt.children)

    def on_toggle_arch(self, arch, checkbox_var):
        dt = self.device_tree
        detached_items = self.detached_items
        all_items = self.all_items
        disabled_arches = self.disabled_arches

        enable = checkbox_var.get()
        if enable:
            # architecture has been enabled
            disabled_arches.remove(arch)
            attached_items = []
            for i, v in detached_items.items():
                if arch in v.tags:
                    parent = v.parent
                    ci = 0
                    for c in dt.get_children(parent):
                        # child index > cur index
                        if all_items[c].index > v.index:
                            break
                        ci += 1

                    dt.move(i, parent, ci)
                    attached_items.append(i)

            for n in attached_items:
                del detached_items[n]
        else:
            # one architecture has been disabled
            disabled_arches.add(arch)
            items = dt.tag_has(arch)
            to_detach = []
            for i in items:
                if not (all_items[i].tags - disabled_arches):
                    # All tags in disabled_arch
                    # Save desc of detach node
                    detached_items[i] = all_items[i]
                    to_detach.append(i)

            if to_detach:
                dt.detach(*to_detach)

        self._update_selection()

    def _on_device_tv_select(self, __):
        self._update_selection()

    def _update_selection(self):
        dt = self.device_tree
        sel = dt.selection()

        if len(sel) != 1:
            selected = None
        else:
            item = sel[0]

            selected = self.all_items[item].qt

        if self.selected != selected:
            self.selected = selected
            self.event_generate("<<QOMTypeSelected>>")
