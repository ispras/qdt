__all__ = [
    "VarNotebook"
  , "VarCombobox"
  , "VarTk"
  , "VarLabel"
  , "VarToplevel"
  , "VarButton"
  , "VarLabelFrame"
  , "VarCheckbutton"
  , "VarMenu"
  , "VarTreeview"
]
from six.moves.tkinter import (
    Tk,
    Menu,
    Label,
    Toplevel,
    Button,
    LabelFrame,
    Checkbutton,
    Variable as TkVariable,
    StringVar
)
from six.moves.tkinter_ttk import (
    Notebook,
    Combobox,
    Treeview
)
from common import (
    Variable
)

variables = (Variable, TkVariable)

class VarCheckbutton(Checkbutton):
    def __init__(self, *args, **kw):
        if "text" in kw:
            self.text_var = kw.pop("text")
            kw["text"] = self.text_var.get()
        else:
            self.text_var = StringVar("")
        Checkbutton.__init__(self, *args, **kw)
        self.text_var.trace_variable("w", self.on_var_changed)

    def on_var_changed(self, *args):
        Checkbutton.config(self, text = self.text_var.get())

class VarLabelFrame(LabelFrame):
    def __init__(self, *args, **kw):
        if "text" in kw:
            self.text_var = kw.pop("text")
            kw["text"] = self.text_var.get()
        else:
            self.text_var = StringVar("")
        LabelFrame.__init__(self, *args, **kw)
        self.text_var.trace_variable("w", self.on_var_changed)

    def on_var_changed(self, *args):
        Label.config(self, text = self.text_var.get())

class VarLabel(Label):
    def __init__(self, *args, **kw):
        # "textvariable" argument has same effect to VarLabel as "text"
        try:
            var = kw.pop("textvariable")
        except KeyError:
            pass
        else:
            if "text" in kw:
                raise RuntimeError('"text" and "textvariable" '
                    'arguments cannot be passed together to a VarLabel'
                )
            kw["text"] = var

        if "text" in kw:
            self.text_var = kw.pop("text")
            kw["text"] = self.text_var.get()
        else:
            self.text_var = StringVar("")
        Label.__init__(self, *args, **kw)
        self.text_var.trace_variable("w", self.on_var_changed)

    def on_var_changed(self, *args):
        Label.config(self, text = self.text_var.get())

class VarButton(Button):
    def __init__(self, *args, **kw):
        if "text" in kw:
            self.text_var = kw.pop("text")
            kw["text"] = self.text_var.get()
        else:
            self.text_var = StringVar("")
        Button.__init__(self, *args, **kw)
        self.text_var.trace_variable("w", self.on_var_changed)

    def on_var_changed(self, *args):
        Button.config(self, text = self.text_var.get())

class VarTk(Tk):
    def __init__(self, **kw):
        Tk.__init__(self, **kw)
        self.var = None

    def on_var_changed(self, *args):
        Tk.title(self, self.var.get())

    def title(self, stringvar = None):
        if not stringvar:
            return self.var

        if stringvar != self.var:
            if self.var:
                self.var.trace_vdelete("w", self.observer_name)
            self.var = stringvar
            self.observer_name = self.var.trace_variable(
                "w",
                self.on_var_changed
            )

            self.on_var_changed()

class VarToplevel(Toplevel):
    def __init__(self, *args, **kw):
        self.var = None
        Toplevel.__init__(self, *args, **kw)

    def on_var_changed(self, *args):
        Toplevel.title(self, self.var.get())

    def title(self, stringvar = None):
        if not stringvar:
            return self.var

        if stringvar != self.var:
            if self.var:
                self.var.trace_vdelete("w", self.observer_name)
            self.var = stringvar
            self.observer_name = self.var.trace_variable(
                "w",
                self.on_var_changed
            )

            self.on_var_changed()


class MenuVarBinding():
    def __init__(self, menu, var, idx, param):
        self.menu, self.var, self.idx, self.param = menu, var, idx, param

    def on_var_changed(self, *args):
        self.menu.on_var_changed(self.var, self.idx, self.param)

class VarMenu(Menu):
    def __init__(self, *args, **kw):
        Menu.__init__(self, *args, **kw)
        if (not "tearoff" in kw) or kw["tearoff"]:
            self.count = 1
        else:
            self.count = 0

    def on_var_changed(self, var, idx, param):
        kwargs = {
            param: var.get()
        }
        Menu.entryconfig(self, idx, **kwargs)

    def add(self, itemType, cnf = {}, **kw):
        # handle variable text only for items which have such parameters
        if itemType in [
            # "radiobutton" - TODO: check it
            "cascade",
            "command",
            "checkbutton"
            # "separator" - does not have such parameters
        ]:
            for param in ["label", "accelerator"]:
                if param in cnf:
                    var = cnf.pop(param)
                elif param in kw:
                    var = kw.pop(param)
                else:
                    var = StringVar()

                binding = MenuVarBinding(self, var, self.count, param)
                var.trace_variable("w", binding.on_var_changed)

                if cnf:
                    cnf[param] = var.get()
                else:
                    kw[param] = var.get()

        self.count = self.count + 1

        Menu.add(self, itemType, cnf or kw)

class TreeviewHeaderBinding():
    def __init__(self, menu, column, var_str):
        self.menu, self.column, self.str = menu, column, var_str

    def on_var_changed(self, *args):
        self.menu.on_var_changed(self.column, self.str.get())

class TreeviewCellBinding():
    def __init__(self, tv, col, row, var):
        self.tv, self.col, self.row, self.var = tv, col, row, var

        self._var = self.var.trace_variable("w", self.on_var_changed)

    def on_var_changed(self, *a):
        values = list(self.tv.item(self.row, "values"))
        values[self.col] = self.var.get()
        self.tv.item(self.row, values = values)

class VarTreeview(Treeview):
    def __init__(self, *args, **kw):
        Treeview.__init__(self, *args, **kw)

    def on_var_changed(self, column, var_str):
        Treeview.heading(self, column, text = var_str)

    def heading(self, column, **kw):
        if "text" in kw:
            text_var = kw.pop("text")
            kw["text"] = text_var.get()
            binding = TreeviewHeaderBinding(self, column, text_var)
            text_var.trace_variable("w", binding.on_var_changed)

        return Treeview.heading(self, column, **kw)

    """ If at least one value is StringVar then the values should be a list, not
    a tuple. """
    def insert(self, *a, **kw):
        to_track = []

        try:
            values = kw["values"]
        except KeyError:
            pass
        else:
            if not isinstance(values, (tuple, list)):
                values = (values,)

            for col, v in enumerate(values):
                if isinstance(v, variables):
                    to_track.append((col, v))
                    values[col] = v.get()

        item_iid = Treeview.insert(self, *a, **kw)

        for col, v in to_track:
            TreeviewCellBinding(self, col, item_iid, v)

        return item_iid

class ComboboxEntryBinding():
    def __init__(self, varcombobox, idx, variable):
        self.vcb = varcombobox
        self.var = variable
        self.cb_id = variable.trace_variable("w", self.on_changed)
        self.idx = idx

    def unbind(self):
        self.var.trace_vdelete(self.cb_id)

    def on_changed(self, *args):
        current_values = Combobox.cget(self.vcb, "values")

        cur = Combobox.current(self.vcb)

        new_values = list(current_values)
        new_values[self.idx] = self.var.get()

        Combobox.config(self.vcb, values = new_values)

        if cur == self.idx:
            Combobox.current(self.vcb, cur)

class VarCombobox(Combobox):
    def __init__(self, *args, **kw):
        self.bindings = []

        if "values" in kw:
            self.set_var_values(kw["values"])
            kw["values"] = [ b.var.get() for b in self.bindings ]

        Combobox.__init__(self, *args, **kw)

    def set_var_values(self, values):
        for b in self.bindings:
            b.unbind()

        self.bindings = [
            ComboboxEntryBinding(self, *v) for v in enumerate(values)
        ]

    def cget(self, key):
        if "values" == key:
            return [ b.var for b in self.bindings ]

        return Combobox.cget(self, key)

    def config(self, cnf = None, **kw):
        if "values" in kw:
            self.set_var_values(kw["values"])
            kw["values"] = [ b.var.get() for b in self.bindings ]

        return Combobox.config(self, cnf, **kw)

class VarNotebook(Notebook):
    def __init__(self, *args, **kw):
        Notebook.__init__(self, *args, **kw)

if __name__ == "__main__":
    root = VarTk()
    root.title(StringVar(value = "Variable widgets test"))
    root.grid()
    root.rowconfigure(0, weight = 1)
    root.columnconfigure(0, weight = 1)

    from .tv_width_helper import (
        TreeviewWidthHelper
    )

    class TestTV(VarTreeview, TreeviewWidthHelper):
        def __init__(self, *args, **kw):
            kw["columns"] = ["0", "1", "2", "3"]
            VarTreeview.__init__(self, *args, **kw)

            TreeviewWidthHelper.__init__(self,
                auto_columns = ["#0"] + kw["columns"]
            )

            for col in kw["columns"]:
                self.column(col, stretch = False)

    tv = TestTV(root)
    tv.grid(row = 0, column = 0, sticky = "NEWS")

    from six.moves.tkinter import (
        BooleanVar,
        IntVar,
        DoubleVar
    )

    sv = StringVar(value = "xxx...")
    bv = BooleanVar(value = True)
    iv = IntVar(value = 0)
    dv = DoubleVar(value = 1.0)

    tv.insert("", 0, values = [sv, bv, iv, dv])
    tv.insert("", 1, values = [bv, iv, dv, sv])
    tv.insert("", 2, values = [iv, dv, sv, bv])
    tv.insert("", 3, values = [dv, sv, bv, iv])

    def update():
        s = sv.get()
        s = s[-1] + s[:-1]
        sv.set(s)
        bv.set(not bv.get())
        iv.set(iv.get() + 1)
        dv.set(dv.get() + 0.1)

        tv.adjust_widths()

        root.after(250, update)

    update()

    root.mainloop()
