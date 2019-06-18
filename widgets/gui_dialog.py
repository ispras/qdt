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

        # Before `master` is changed during the loop below
        self.transient(master.winfo_toplevel())

        self._result = None
        self._alive = True

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

        self.grab_set()

    def __on_destroy(self, e, **kw):
        if e.widget is self:
            self.hk.enable_hotkeys()
        self._alive = False

    def wait(self):
        "Grabs control until the dialog destroyed. Returns a value."

        while self._alive:
            self.update()
            self.update_idletasks()

        return self._result
