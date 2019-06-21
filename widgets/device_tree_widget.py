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
        ysb.grid(row = 0, column = 1, sticky = "NS")
        xsb.grid(row = 1, column = 0, sticky = "EW")

        self.add_button = VarButton(
            self,
            text = _("Select"),
            command = self.on_select_qom_type
        )
        self.add_button.grid(row = 1, column = 2, sticky = "WE")
        self.add_button.config(state = "disabled")

        self.fr = VarLabelFrame(self, text = _("Select QOM type"))
        self.fr.grid(row = 0, column = 2, sticky = "SEWN")

        # Check exception before __init__ call.
        bp = root.mach.project.build_path
        qvd = qvd_get(bp, version = root.mach.project.target_version)
        # the QOM type of roots[0] is "device"
        roots = qvd.qvc.device_tree[0]["children"]
        self.qom_create_tree("", roots)

    def qom_create_tree(self, parent_id, dt_list):
        dt_list.sort(key = lambda x: x["type"])
        for dict_dt in dt_list:
            if "macro" in dict_dt:
                value = ""
                for macro in dict_dt["macro"]:
                    value = value + " " + macro
            else:
                value= "None"
            tr_id = self.device_tree.insert(parent_id, "end",
                text = dict_dt["type"],
                values = value
            )
            if "children" in dict_dt:
                self.qom_create_tree(tr_id, dict_dt["children"])

    def on_select_qom_type(self):
        self.qom_type_var.set(self.v.get())
        self.destroy()

    # write selected qom type in qom_type_var
    def on_b1_press_dt(self, event):
        item = self.device_tree.identify('item', event.x, event.y)

        if not item:
            return

        self.add_button.config(state = "active")
        for widget in self.fr.winfo_children():
            widget.destroy()

        dt_type = self.device_tree.item(item, "text")
        self.v = StringVar()
        self.v.set(dt_type)

        b = Radiobutton(self.fr,
            text = dt_type,
            variable = self.v,
            value = dt_type
        )
        b.pack(anchor = "w")

        macros = self.device_tree.item(item, "values")[0]
        if not macros == "None":
            l = macros.split(" ")
            for mstr in l:
                b = Radiobutton(
                    self.fr,
                    text = mstr,
                    variable = self.v,
                    value = mstr
                )
                b.pack(anchor = "w")

        b.select()
