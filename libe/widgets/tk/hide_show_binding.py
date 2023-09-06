__all__ = [
    "HideShowBinding"
]


class HideShowBinding(object):
    """Binds a Tkinter compatible `variable` with visibility state of a
Tkinter compatible `toplevel` window.
    """

    def __init__(self, toplevel, variable):
        self._v = variable
        self._t = toplevel

        self._showed = None

        toplevel.wm_protocol("WM_DELETE_WINDOW", self._on_wm_delete_window)

        self._on_map_b = toplevel.bind("<Map>", self._on_map, "+")
        self._on_unmap_b = toplevel.bind("<Unmap>", self._on_unmap, "+")
        self._on_destroy_b = toplevel.bind(
            "<Destroy>", self._on_destroy, "+"
        )

        variable.trace_variable("w", self._on_w)

        self.showed = toplevel.winfo_ismapped()

    @property
    def showed(self):
        return self._showed

    @showed.setter
    def showed(self, showed):
        showed = bool(showed)
        if showed is self._showed:
            return
        self._showed = showed

        t = self._t
        if showed:
            self._v.set(True)
            if t is not None:
                t.deiconify()
        else:
            self._v.set(False)
            if t is not None:
                t.withdraw()

    @property
    def hidden(self):
        return not self._showed

    @hidden.setter
    def hidden(self, hidden):
        self.showed = not hidden

    @property
    def variable(self):
        return self._v

    # TODO: @variable.setter

    @property
    def toplevel(self):
        return self._t

    # TODO: @toplevel.setter

    def _on_wm_delete_window(self):
        if self._t is not None:
            self.showed = False

    def _on_map(self, e):
        if e.widget is self._t:
            self.showed = True

    def _on_unmap(self, e):
        if e.widget is self._t:
            self.showed = False

    def _on_destroy(self, e):
        t = self._t
        if e.widget is t:
            self._t = None

            t.unbind(self._on_map_b)
            del self._on_map_b
            t.unbind(self._on_unmap_b)
            del self._on_unmap_b
            t.unbind(self._on_destroy_b)
            del self._on_destroy_b

            # TODO: how to "unbind" `_on_wm_delete_window`?

    def _on_w(self, *__):
        self.showed = self._v.get()
