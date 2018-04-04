__all__ = [
    "GUIDialog"
]

from .gui_toplevel import (
    GUIToplevel
)

class GUIDialog(GUIToplevel):
    def __init__(self, *args, **kw):
        GUIToplevel.__init__(self, *args, **kw)

        master = self.master

        while master:
            top = master.winfo_toplevel()
            try:
                hk = top.hk
            except AttributeError:
                master = top.master
            else:
                hk.disable_hotkeys()
                self.bind("<Destroy>", self.__on_destroy, "+")
                self.hk = hk
                break
        else:
            # Those imports are only used there.
            from common import (
                mlget as _
            )

            import sys

            sys.stderr.write(_(
                "Cannot found a top level window with hot key context\n"
            ).get())

        self.transient(master)
        self.grab_set()

    def __on_destroy(self, e, **kw):
        if e.widget is self:
            self.hk.enable_hotkeys()
