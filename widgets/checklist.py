__all__ = [
    "Checklist"
]


from six.moves.tkinter import (
    BooleanVar,
    X
)
from .gui_frame import (
    GUIFrame
)
from .var_widgets import (
    VarCheckbutton
)


class Checklist(GUIFrame):
    """ Column of check boxes with labels.

"<<Check>>" event is generated when the state of a check box changes.
During event handling, `current` attribute refers to the string used to build
the check box label.
    """

    def __init__(self, master, items, *a, **kw):
        GUIFrame.__init__(self, master, *a, **kw)

        self._mapping = mapping = {}

        for row, text in enumerate(items):
            v = BooleanVar()
            c = VarCheckbutton(self, text = text, variable = v)
            c.grid(row = row, column = 0, sticky = "W")

            def trace(_, __, ___, _text = text):
                self.current = _text
                self.event_generate("<<Check>>")
                del self.current

            trace_id = v.trace_variable("w", trace)

            mapping[text] = (v, c, trace_id)

    @property
    def checked(self):
        "`set` of strings whose check boxes are currently checked."
        return set(text for text, v in self._mapping.items() if v[0].get())

    @property
    def unchecked(self):
        "`set` of strings whose check boxes are currently unchecked."
        return set(text for text, v in self._mapping.items() if not v[0].get())

    def get(self, item):
        return self._mapping[item][0].get()

    def set(self, checked, items):
        mapping = self._mapping
        for i in items:
            var = mapping[i][0]
            if var.get() != checked:
                var.set(checked)

    def select(self, items):
        self.set(True, items)

    def unselect(self, items):
        self.set(True, items)

    def select_all(self):
        self.set(True, self._mapping.keys())

    def unselect_all(self):
        self.set(False, self._mapping.keys())

    def invert_selection(self):
        for v in self._mapping.values():
            v[0].set(not v[0].get())
