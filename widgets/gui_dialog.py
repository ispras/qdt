__all__ = [ "GUIDialog" ]

from .var_widgets import VarToplevel

class GUIDialog(VarToplevel):
    def __init__(self, *args, **kw):
        VarToplevel.__init__(self, *args, **kw)

        master = self.master

        try:
            hk = master.winfo_toplevel().hk
        except:
            hk = None
        else:
            hk.disable_hotkeys()
            self.bind("<Destroy>", self.__on_destroy, "+")
            self.hk = hk

        self.transient(master)
        self.grab_set()

    def __on_destroy(self, e, **kw):
        if e.widget is self:
            self.hk.enable_hotkeys()
