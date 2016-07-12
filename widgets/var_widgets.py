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
