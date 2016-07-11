from Tkinter import Tk, Menu, StringVar

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

class MenuVarBinding():
    def __init__(self, menu, var, idx):
        self.menu, self.var, self.idx = menu, var, idx

    def on_var_changed(self, *args):
        self.menu.on_var_changed(self.var, self.idx)

class VarMenu(Menu):
    def __init__(self, *args, **kw):
        Menu.__init__(self, *args, **kw)
        if (not "tearoff" in kw) or kw["tearoff"]:
            self.count = 1
        else:
            self.count = 0

    def on_var_changed(self, var, idx):
        Menu.entryconfig(self, idx, label = var.get())

    def add(self, itemType, cnf = {}, **kw):
        if "label" in cnf:
            label = cnf.pop("label")
        elif "label" in kw:
            label = kw.pop("label")
        else:
            label = StringVar()

        binding = MenuVarBinding(self, label, self.count)
        self.count = self.count + 1

        label.trace_variable("w", binding.on_var_changed)

        if cnf:
            cnf["label"] = label.get()
        else:
            kw["label"] = label.get()

        Menu.add(self, itemType, cnf or kw)

        binding.on_var_changed()