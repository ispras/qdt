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
    Radiobutton,
    Checkbutton,
    StringVar
)
from common import (
    mlget as _
)
from .gui_dialog import (
    GUIDialog
)
from .scrollframe import (
    add_scrollbars_with_tags,
    add_scrollbars_native
)
from .gui_frame import (
    GUIFrame
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

        dt.bind("<ButtonPress-1>", self.on_b1_press_dt)
        add_scrollbars_native(self, dt)

        dt.grid(
            row = 0,
            column = 0,
            rowspan = 3,
            sticky = "NEWS"
        )

        column_fr = VarLabelFrame(self, borderwidth = 0)
        column_fr.grid(row = 0, column = 2, rowspan = 2, sticky = "SEWN")
        column_fr.columnconfigure(0, weight = 1)
        column_fr.rowconfigure(0, weight = 1)
        column_fr.rowconfigure(1, weight = 1, minsize = 100)

        fr_at = VarLabelFrame(column_fr, text = _("Architecture filter"))
        fr_at.grid(row = 0, column = 0, sticky = "SEWN")

        self.fr_qt = VarLabelFrame(column_fr, text = _("Select QOM type"))
        self.fr_qt.grid(row = 1, column = 0, sticky = "SEWN")

        self.add_button = VarButton(
            column_fr,
            text = _("Select"),
            command = self.on_select_qom_type
        )
        self.add_button.grid(row = 2, column = 0, sticky = "EW")
        self.add_button.config(state = "disabled")

        qtype_dt = self.qtype_dt = qvd_get(
            root.mach.project.build_path,
            version = root.mach.project.target_version
        ).qvc.device_tree

        arch_buttons = VarLabelFrame(fr_at, borderwidth = 0)
        arch_buttons.pack(fill = "x")

        arch_buttons.columnconfigure(0, weight = 1, minsize = 60)
        arch_buttons.columnconfigure(1, weight = 1, minsize = 60)
        arch_buttons.columnconfigure(2, weight = 1, minsize = 60)

        bt_all_arches = VarButton(
            arch_buttons,
            text = _("All"),
            command = self.select_arches
        )
        bt_all_arches.grid(row = 0, column = 0, sticky = "EW")

        bt_none_arches = VarButton(
            arch_buttons,
            text = _("None"),
            command = self.deselect_arches
        )
        bt_none_arches.grid(row = 0, column = 1, sticky = "EW")

        bt_invert_arches = VarButton(
            arch_buttons,
            text = _("Invert"),
            command = self.invert_arches
        )
        bt_invert_arches.grid(row = 0, column = 2, sticky = "EW")

        if not qtype_dt.arches:
            bt_all_arches.config(state = "disabled")
            bt_none_arches.config(state = "disabled")
            bt_invert_arches.config(state = "disabled")

        arch_selector = VarLabelFrame(fr_at, borderwidth = 0)
        arch_selector.pack(fill = "both", anchor = "w")
        arch_selector, scrolltag = add_scrollbars_with_tags(
            arch_selector, GUIFrame
        )

        av = self.arches_vars = []
        ac = self.arches_checkbox = []
        for i, a in enumerate(sorted(list(qtype_dt.arches))):
            var = StringVar()
            c = Checkbutton(arch_selector,
                text = a,
                variable = var,
                onvalue = a,
                offvalue = "",
                command = self.on_select_arch_type
            )
            c.grid(row = i, column = 0, sticky = "W")
            c.bindtags((scrolltag,) + c.bindtags())
            c.select()
            av.append(var)
            ac.append(c)

        # Counter of Disabled Arch
        self.cda = 0

        # key: item
        # value: (parent, index, tags)
        self.detach_items = {}
        self.dt_items = {}

        self.qom_create_tree("", qtype_dt.children)

    def select_arches(self):
        dt_items = self.dt_items
        dt = self.device_tree
        for i, v in self.detach_items.items():
            parent = v[0]
            ci = 0
            for c in dt.get_children(parent):
                # child index > cur index
                if dt_items[c][1] > v[1]:
                    break
                ci += 1

            dt.move(i, parent, ci)

        self.detach_items = {}

        self.cda = 0

        for c in self.arches_checkbox:
            c.select()

    def deselect_arches(self):
        dt = self.device_tree

        detach_items = []
        for i in self.dt_items:
            if i not in self.detach_items:
                detach_items.append(i)
                self.detach_items[i] = self.dt_items[i]
        else:
            dt.detach(*detach_items)

        for c in self.arches_checkbox:
            c.deselect()

        self.cda = len(self.qtype_dt.arches)

    def invert_arches(self):
        for c in self.arches_checkbox:
            c.invoke()

    def qom_create_tree(self, parent_id, qt_children):
        dt = self.device_tree
        dt_items = self.dt_items

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
            dt_items[cur_id] = (parent_id, i, set(qt.arches))
            if qt.children:
                self.qom_create_tree(cur_id, qt.children)

    def on_select_arch_type(self):
        included_arches = set()
        for v in self.arches_vars:
            arch_str = v.get()
            if arch_str != "":
                included_arches.add(arch_str)

        disabled_arches = self.qtype_dt.arches - included_arches
        detach_items = []

        dt = self.device_tree
        new_cda = len(disabled_arches)

        di = self.detach_items
        dt_items = self.dt_items
        if new_cda > self.cda:
            # one architecture has been disabled
            for a in disabled_arches:
                items = dt.tag_has(a)
                for i in items:
                    if not(dt_items[i][2] - disabled_arches) and i not in di:
                        # All tags in disabled_arch
                        # Save desc of detach node
                        di[i] = dt_items[i]
                        detach_items.append(i)

            if detach_items:
                dt.detach(*detach_items)
        else:
            # one architecture has been enabled
            del_nodes = []
            for i, v in di.items():
                if v[2].intersection(included_arches):
                    parent = v[0]
                    ci = 0
                    for c in dt.get_children(parent):
                        # child index > cur index
                        if dt_items[c][1] > v[1]:
                            break
                        ci += 1

                    dt.move(i, parent, ci)
                    del_nodes.append(i)

            for n in del_nodes:
                del di[n]

        self.cda = new_cda

    def on_select_qom_type(self):
        self.qom_type_var.set(self.v.get())
        self.destroy()

    # write selected qom type in qom_type_var
    def on_b1_press_dt(self, event):
        item = self.device_tree.identify('item', event.x, event.y)

        if not item:
            return

        self.add_button.config(state = "normal")
        for widget in self.fr_qt.winfo_children():
            widget.destroy()

        dt_type = self.device_tree.item(item, "text")
        self.v = StringVar()
        self.v.set(dt_type)

        b = Radiobutton(self.fr_qt,
            text = dt_type,
            variable = self.v,
            value = dt_type
        )
        b.pack(anchor = "w")

        macros = self.device_tree.item(item, "values")[0]
        if macros != "None":
            l = macros.split(", ")
            for mstr in l:
                b = Radiobutton(
                    self.fr_qt,
                    text = mstr,
                    variable = self.v,
                    value = mstr
                )
                b.pack(anchor = "w")

        b.select()
