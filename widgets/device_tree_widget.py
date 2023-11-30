__all__ = [
    "DeviceTreeWidget"
]

from .var_widgets import (
    VarTreeview,
    VarButton,
    VarLabelFrame
)
from qemu import (
    qvd_get
)
from six.moves.tkinter import (
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


ItemDesc = namedtuple(
    "ItemDesc",
    "parent index tags"
)


class DeviceTreeWidget(GUIDialog):
    def __init__(self, root, *args, **kw):
        GUIDialog.__init__(self, master = root, *args, **kw)
        self.qom_type_var = root.qom_type_var

        self.title(_("Device Tree"))
        self.grid()

        self.columnconfigure(0, weight = 1, minsize = 300)
        self.columnconfigure(2, weight = 1, minsize = 100)
        self.rowconfigure(0, weight = 1)

        geom = "+" + str(int(root.winfo_rootx())) \
             + "+" + str(int(root.winfo_rooty()))
        self.geometry(geom)

        self.focus()

        self.device_tree = dt = VarTreeview(self, selectmode = "browse")
        dt["columns"] = "Macros"

        dt.heading("#0", text = _("Devices"))
        dt.heading("Macros", text = _("Macros"))

        dt.bind("<<TreeviewSelect>>", self._on_device_tv_select, "+")
        self.v_sel_type = v_sel_type = StringVar(self)

        dt.grid(
            row = 0,
            column = 0,
            sticky = "NEWS"
        )

        add_scrollbars_native(self, dt)

        column_fr = Frame(self, borderwidth = 0)
        column_fr.grid(row = 0, column = 2, rowspan = 2, sticky = "SEWN")
        column_fr.columnconfigure(0, weight = 1)
        column_fr.rowconfigure(0, weight = 1)
        column_fr.rowconfigure(1, weight = 1, minsize = 100)

        fr_at = VarLabelFrame(column_fr, text = _("Architecture filter"))
        fr_at.grid(row = 0, column = 0, sticky = "SEWN")

        self.fr_qt = VarLabelFrame(column_fr, text = _("Select QOM type"))
        self.fr_qt.grid(row = 1, column = 0, sticky = "SEWN")

        self.bt_select = VarButton(
            column_fr,
            text = _("Select"),
            command = self._on_bt_select
        )
        self.bt_select.grid(row = 2, column = 0, sticky = "EW")
        self.bt_select.config(state = DISABLED)
        v_sel_type.trace("w", self._on_v_sel_type_w)

        qtype_dt = self.qtype_dt = qvd_get(
            root.mach.project.build_path,
            version = root.mach.project.target_version
        ).qvc.device_tree

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

        if not qtype_dt.arches:
            bt_all_arches.config(state = "disabled")
            bt_none_arches.config(state = "disabled")
            bt_invert_arches.config(state = "disabled")

        arch_selector_outer = Frame(fr_at, borderwidth = 0)
        arch_selector_outer.pack(fill = "both", anchor = "w")
        arch_selector, scrolltag = add_scrollbars_with_tags(
            arch_selector_outer, GUIFrame
        )

        ac = self.arches_checkbox = []
        for a in sorted(list(qtype_dt.arches)):
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

        self.qom_create_tree("", qtype_dt.children)

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

    def deselect_arches(self):
        dt = self.device_tree

        to_detach = []
        for i in self.all_items:
            if i not in self.detached_items:
                to_detach.append(i)
                self.detached_items[i] = self.all_items[i]

        dt.detach(*to_detach)
        self.disabled_arches = set(self.qtype_dt.arches)

        for c in self.arches_checkbox:
            c.deselect()

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

            all_items[cur_id] = ItemDesc(parent_id, i, set(qt.arches))

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

    def _on_bt_select(self):
        self.qom_type_var.set(self.v_sel_type.get())
        self.destroy()

    # write selected qom type in qom_type_var
    def _on_device_tv_select(self, __):
        dt = self.device_tree
        sel = dt.selection()

        if len(sel) != 1:
            return

        item = sel[0]

        for widget in self.fr_qt.winfo_children():
            widget.destroy()

        dt_type = dt.item(item, "text")

        v_sel_type = self.v_sel_type
        # Note, value of `v_sel_type` will be assigned automatically by
        # `Radiobutton`s `select` below.

        b = Radiobutton(self.fr_qt,
            text = dt_type,
            variable = v_sel_type,
            value = dt_type
        )
        b.pack(anchor = "w")

        macros = dt.item(item, "values")[0]
        if macros != "None":
            l = macros.split(", ")
            for mstr in l:
                b = Radiobutton(
                    self.fr_qt,
                    text = mstr,
                    variable = v_sel_type,
                    value = mstr
                )
                b.pack(anchor = "w")

        b.select()

    def _on_v_sel_type_w(self, *__):
        v_sel_type = self.v_sel_type
        if v_sel_type.get():
            self.bt_select.config(state = NORMAL)
        else:
            self.bt_select.config(state = DISABLED)
