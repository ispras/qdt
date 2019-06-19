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

class DeviceTreeWidget(GUIDialog):
    def __init__(self, root, *args, **kw):
        GUIDialog.__init__(self, master = root, *args, **kw)
        self.qom_type_var = root.qom_type_var

        self.title(_("Device Tree"))
        self.grid()
        
        self.columnconfigure(0, weight = 1)
        self.rowconfigure(0, weight = 1)

        self.columnconfigure(2, minsize = 200)

        geom = "+" + str(int(root.winfo_rootx())) \
             + "+" + str(int(root.winfo_rooty()))
        self.geometry(geom)

        self.focus()

        self.device_tree = VarTreeview(self)
        self.device_tree["columns"] = ("Macros")

        self.device_tree.heading("#0", text = _("Devices"))
        self.device_tree.heading("Macros", text = _("Macros"))

        self.device_tree.bind("<ButtonPress-1>", self.on_b1_press_dt)

        self.device_tree.grid(
            row = 0,
            column = 0,
            rowspan = 3,
            sticky = "NEWS"
        )

        #Add Scrollbar
        ysb = Scrollbar(self,
            orient = "vertical",
            command = self.device_tree.yview
        )
        xsb = Scrollbar(self,
            orient = "horizontal",
            command = self.device_tree.xview
        )
        self.device_tree['yscroll'] = ysb.set
        self.device_tree['xscroll'] = xsb.set
        ysb.grid(row = 0, column = 1, rowspan = 3, sticky = "NS")
        xsb.grid(row = 3, column = 0, sticky = "EW")

        self.add_button = VarButton(
            self,
            text = _("Select"),
            command = self.on_select_qom_type
        )
        self.add_button.grid(row = 2, rowspan = 2, column = 2, sticky = "WE")
        self.add_button.config(state = "disabled")

        self.fr_qt = VarLabelFrame(self, text = _("Select QOM type"))
        self.fr_qt.grid(row = 0, column = 2, sticky = "SEWN")

        self.fr_at = VarLabelFrame(self, text = _("Select arch filter"))
        self.fr_at.grid(row = 1, column = 2, sticky = "SEWN")

        qtype_dt = self.qtype_dt = qvd_get(
            root.mach.project.build_path,
            version = root.mach.project.target_version
        ).qvc.device_tree

        self.arch_vars = []
        for a in sorted(list(qtype_dt.arches)):
            var = StringVar()
            c = Checkbutton(self.fr_at,
                text = a,
                variable = var,
                onvalue = a,
                offvalue = '',
                command = self.on_select_arch_type
            )
            c.pack(anchor = "w")
            self.arch_vars.append(var)
            c.select()

        # Counter of Disabled Arch
        self.cda = 0

        # list of tuple(item, parent, index, tags) with desc detached nodes
        self.detach_nodes = []

        self.qom_create_tree("", qtype_dt.children)

    def qom_create_tree(self, parent_id, dt):
        for key in sorted(dt.keys()):
            qt = dt[key]
            if qt.macros:
                value = ",".join(qt.macros)
            else:
                value = "None"

            cur_id = self.device_tree.insert(parent_id, "end",
                text = qt.name,
                values = value,
                tags = list(qt.arches)
            )
            if qt.children:
                self.qom_create_tree(cur_id, qt.children)

    def on_select_arch_type(self):
        included_arch = set()
        for v in self.arch_vars:
            arch_str = v.get()
            if arch_str != '':
                included_arch.add(arch_str)

        disabled_arch = self.qtype_dt.arches - included_arch
        detach_items = []

        new_cda = len(disabled_arch)
        if new_cda > self.cda:
            # one or more of architectures has been disabled
            for a in disabled_arch:
                nodes = self.device_tree.tag_has(a)
                for n in nodes:
                    cur_tags = set(self.device_tree.item(n, option = "tags"))
                    if not(cur_tags - disabled_arch):
                        # All tags in disabled_arch
                        # Save desc of detach node
                        self.detach_nodes.append((
                            n,
                            self.device_tree.parent(n),
                            self.device_tree.index(n),
                            cur_tags
                        ))
                        detach_items.append(n)

            if detach_items:
                self.device_tree.detach(*detach_items)
        else:
            # one or more of architectures has been enabled
            for n_desc in self.detach_nodes:
                if n_desc[3].intersection(included_arch):
                    self.device_tree.move(n_desc[0], n_desc[1], n_desc[2])

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
