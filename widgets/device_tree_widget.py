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
from six.moves.tkinter_ttk import (
    Scrollbar
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
    add_scrollbars
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

        self.rowconfigure(1, weight = 1, minsize = 100)
        self.rowconfigure(0, weight = 1, minsize = 50)

        geom = "+" + str(int(root.winfo_rootx())) \
             + "+" + str(int(root.winfo_rooty()))
        self.geometry(geom)

        self.focus()

        self.device_tree = dt = VarTreeview(self)
        dt["columns"] = ("Macros")

        dt.heading("#0", text = _("Devices"))
        dt.heading("Macros", text = _("Macros"))

        dt.bind("<ButtonPress-1>", self.on_b1_press_dt)

        dt.grid(
            row = 0,
            column = 0,
            rowspan = 3,
            sticky = "NEWS"
        )

        #Add Scrollbar
        ysb = Scrollbar(self,
            orient = "vertical",
            command = dt.yview
        )
        xsb = Scrollbar(self,
            orient = "horizontal",
            command = dt.xview
        )
        dt['yscroll'] = ysb.set
        dt['xscroll'] = xsb.set
        ysb.grid(row = 0, column = 1, rowspan = 3, sticky = "NS")
        xsb.grid(row = 3, column = 0, sticky = "EW")

        self.add_button = VarButton(
            self,
            text = _("Select"),
            command = self.on_select_qom_type
        )
        self.add_button.grid(row = 2, column = 2, sticky = "EW")
        self.add_button.config(state = "disabled")

        self.fr_qt = VarLabelFrame(self, text = _("Select QOM type"))
        self.fr_qt.grid(row = 1, column = 2, sticky = "SEWN")

        self.fr_at = VarLabelFrame(self, text = _("Select arch filter"))
        self.fr_at.grid(row = 0, column = 2, sticky = "SEWN")
        self.fr_at = add_scrollbars(self.fr_at, GUIFrame)

        qtype_dt = self.qtype_dt = qvd_get(
            root.mach.project.build_path,
            version = root.mach.project.target_version
        ).qvc.device_tree

        self.arch_vars = []
        self.arches_checkbox = []

        self.fr_at.columnconfigure(0, minsize = 60)
        self.fr_at.columnconfigure(1, minsize = 60)
        self.fr_at.columnconfigure(2, minsize = 60)

        bt_all_arches = VarButton(
            self.fr_at,
            text = _("All"),
            command = self.select_arches
        )
        bt_all_arches.grid(row = 0, column = 0, sticky = "WE")

        bt_none_arches = VarButton(
            self.fr_at,
            text = _("None"),
            command = self.deselect_arches
        )
        bt_none_arches.grid(row = 0, column = 1, sticky = "WE")

        bt_invert_arches = VarButton(
            self.fr_at,
            text = _("Invert"),
            command = self.invert_arches
        )
        bt_invert_arches.grid(row = 0, column = 2, sticky = "WE")

        if not qtype_dt.arches:
            bt_all_arches.config(state = "disabled")
            bt_none_arches.config(state = "disabled")
            bt_invert_arches.config(state = "disabled")

        i = 1
        for a in sorted(list(qtype_dt.arches)):
            var = StringVar()
            c = Checkbutton(self.fr_at,
                text = a,
                variable = var,
                onvalue = a,
                offvalue = '',
                command = self.on_select_arch_type
            )
            c.grid(row = i, column = 0, columnspan = 3, sticky = "W")
            i += 1
            c.select()
            self.arch_vars.append(var)
            self.arches_checkbox.append(c)

        # Counter of Disabled Arch
        self.cda = 0

        # key: item
        # value: (parent, index, tags)
        self.detach_items = {}
        self.dt_items = {}

        self.qom_create_tree("", qtype_dt.children)

    def select_arches(self):
        self.in_callback = True
        for i, v in self.detach_items.items():
            self.device_tree.move(i, v[0], v[1])

        self.detach_items = {}

        self.cda = 0

        for c in self.arches_checkbox:
            c.select()
        self.in_callback = False

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
        for key in sorted(qt_children.keys()):
            qt = qt_children[key]
            if qt.macros:
                value = ",".join(qt.macros)
            else:
                value = "None"

            cur_id = dt.insert(parent_id, "end",
                text = qt.name,
                values = value,
                tags = list(qt.arches)
            )
            dt_items[cur_id] = (parent_id, dt.index(cur_id), set(qt.arches))
            if qt.children:
                self.qom_create_tree(cur_id, qt.children)

    def on_select_arch_type(self):
        included_arches = set()
        for v in self.arch_vars:
            arch_str = v.get()
            if arch_str != '':
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
                    dt.move(i, v[0], v[1])
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

        self.add_button.config(state = "active")
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
            l = macros.split(",")
            for mstr in l:
                b = Radiobutton(
                    self.fr_qt,
                    text = mstr,
                    variable = self.v,
                    value = mstr
                )
                b.pack(anchor = "w")

        b.select()
