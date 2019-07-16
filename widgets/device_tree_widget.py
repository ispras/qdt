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
    StringVar
)
from common import (
    mlget as _
)
from .gui_dialog import (
    GUIDialog
)
from .scrollframe import (
    add_scrollbars_native
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

        self.device_tree = dt = VarTreeview(self)
        dt["columns"] = "Macros"

        dt.heading("#0", text = _("Devices"))
        dt.heading("Macros", text = _("Macros"))

        dt.bind("<ButtonPress-1>", self.on_b1_press_dt)
        add_scrollbars_native(self, dt)

        dt.grid(
            row = 0,
            column = 0,
            sticky = "NEWS"
        )

        self.add_button = VarButton(
            self,
            text = _("Select"),
            command = self.on_select_qom_type
        )
        self.add_button.grid(row = 1, column = 2, sticky = "WE")
        self.add_button.config(state = "disabled")

        self.fr_qt = VarLabelFrame(self, text = _("Select QOM type"))
        self.fr_qt.grid(row = 0, column = 2, sticky = "SEWN")

        qtype_dt = qvd_get(
            root.mach.project.build_path,
            version = root.mach.project.target_version
        ).qvc.device_tree

        self.qom_create_tree("", qtype_dt.children)

    def qom_create_tree(self, parent_id, qt_children):
        dt = self.device_tree

        for key in sorted(qt_children.keys()):
            qt = qt_children[key]
            if qt.macros:
                value = ", ".join(qt.macros)
            else:
                value = "None"

            cur_id = dt.insert(parent_id, "end",
                text = qt.name,
                values = (value, ),
            )
            if qt.children:
                self.qom_create_tree(cur_id, qt.children)

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
