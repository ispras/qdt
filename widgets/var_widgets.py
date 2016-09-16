from Tkinter import \
    Tk, \
    Menu, \
    Label, \
    Toplevel, \
    Button, \
    LabelFrame, \
    Checkbutton, \
    StringVar

from ttk import \
    Treeview

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

class TreeViewVarBinding():
    def __init__(self, menu, column, var_str):
        self.menu, self.column, self.str = menu, column, var_str

    def on_var_changed(self, *args):
        self.menu.on_var_changed(self.column, self.str.get())

class VarTreeView(Treeview):
    def __init__(self, *args, **kw):
        Treeview.__init__(self, *args, **kw)

    def on_var_changed(self, column, var_str):
        Treeview.heading(self, column, text = var_str)

    def heading(self, column, **kw):
        if "text" in kw:
            text_var = kw.pop("text")
            kw["text"] = text_var.get()
            binding = TreeViewVarBinding(self, column, text_var)
            text_var.trace_variable("w", binding.on_var_changed)

        Treeview.heading(self, column, **kw)

