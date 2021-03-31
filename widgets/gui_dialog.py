__all__ = [
    "GUIDialog"
]


from .gui_toplevel import (
    GUIToplevel
)


class GUIDialog(GUIToplevel):

    def __init__(self, *args, **kw):
        GUIToplevel.__init__(self, *args, **kw)

        self.transient(self.master.winfo_toplevel())

        self._result = None
        self._alive = True

        self.bind("<Destroy>", self.__on_destroy, "+")

        self._enable_hk = False
        try:
            hk = self.hk
        except:
            # Those imports are only used there.
            from common import (
                mlget as _
            )

            import sys

            sys.stderr.write(_(
                "Cannot found a top level window with hot key context\n"
            ).get())
        else:
            if hk.enabled:
                hk.disable_hotkeys()
                self._enable_hk = True
            else:
                # Do not enable hotkeys after operation if they are
                # disabled now.
                pass

        # window needs to be visible for the grab
        # See: https://stackoverflow.com/questions/40861638/python-tkinter-treeview-not-allowing-modal-window-with-direct-binding-like-on-ri
        self.wait_visibility()
        self.grab_set()

    def __on_destroy(self, e, **kw):
        if e.widget is not self:
            return
        if self._enable_hk:
            self.hk.enable_hotkeys()
        self._alive = False

    def wait(self):
        "Grabs control until the dialog destroyed. Returns a value."

        while self._alive:
            self.update()
            self.update_idletasks()

        return self._result
