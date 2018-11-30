#!/usr/bin/python2

from widgets import (
    VarCombobox,
    VarTk,
    VarLabel
)
from six.moves.tkinter import (
    StringVar
)
from random import (
    random
)

class VarComboboxTest(VarCombobox):
    def __init__(self, *args, **kw):
        VarCombobox.__init__(self, *args, **kw)
        self.after(0, self.on_tick)

    def on_tick(self):
        for v in self.cget("values"):
            v.set(str(random()))

        self.after(3000, self.on_tick)

if __name__ == "__main__":
    root = VarTk()

    root.title(StringVar(value = "VarCombobox test"))

    VarComboboxTest(root,
        values = [ StringVar() for i in range(0, 10) ]
    ).pack()

    v = StringVar()

    VarComboboxTest(root,
        values = [ StringVar() for i in range(0, 10) ],
        state = "readonly",
        textvariable = v
    ).pack()

    VarLabel(root, text = v).pack()

    root.mainloop()
