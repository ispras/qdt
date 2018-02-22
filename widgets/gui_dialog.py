__all__ = [ "GUIDialog" ]

from .var_widgets import VarToplevel

class GUIDialog(VarToplevel):
    def __init__(self, *args, **kw):
        VarToplevel.__init__(self, *args, **kw)

        self.transient(self.master)
        self.grab_set()
