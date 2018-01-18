__all__ = ["GUIToplevel"]

from .var_widgets import VarToplevel
from .logo import set_logo

class GUIToplevel(VarToplevel):
    def __init__(self, *args, **kw):
        VarToplevel.__init__(self, *args, **kw)

        set_logo(self)
