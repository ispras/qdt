#!/usr/bin/python2

from common import \
    HistoryTracker, \
    InverseOperation, \
    History, \
    HistoryTracker, \
    ML as _

from widgets import \
    CanvasDnD, \
    VarTk, \
    VarMenu, \
    HotKey, \
    HotKeyBinding

import Tkinter as tk
from duplicity.diffdir import tracker

class DnDOperation(InverseOperation):
    def __init__(self, cnv, id, *args, **kwargs):
        InverseOperation.__init__(self, *args, **kwargs)
        self.cnv = cnv
        self.id = id

        self.orig_pos = self.cnv.canvas.coords(self.id)[:2]
        self.target_pos = None

    def __backup__(self):
        self.target_pos = self.cnv.canvas.coords(self.id)[:2]

    def __write_set__(self):
        return [self.id]

    def __read_set__(self):
        return []

    def apply(self, pos):
        points = self.cnv.canvas.coords(self.id)
        anchor = points[:2]

        for idx, p in enumerate(points):
            offset = p - anchor[idx % 2]
            points[idx] = offset + pos[idx % 2]

        apply(self.cnv.canvas.coords, [self.id] + points)

    def __do__(self):
        self.apply(self.target_pos)

    def __undo__(self):
        self.apply(self.orig_pos)

class HistCanvasDnD(CanvasDnD):
    def __init__(self, *args, **kwargs):
        self.ht = kwargs.pop("history_tracker")
        CanvasDnD.__init__(self, *args, **kwargs)

        self.bind('<<DnDDown>>', self.dnd_down)
        self.bind('<<DnDUp>>', self.dnd_up)

    def dnd_down(self, event):
        dragged = self.canvas.find_withtag(tk.CURRENT)[0]

        self.ht.stage(DnDOperation, self,  dragged)

    def dnd_up(self, event):
        self.ht.commit()

def undo():
    if tracker.can_undo():
        tracker.undo()

def redo():
    if tracker.can_do():
        tracker.do()

def reg_hotkeys():
    hotkeys.add_bindings([
        HotKeyBinding(
            callback = undo,
            key_code = 52 # Z
        ),
        HotKeyBinding(
            callback = redo,
            key_code = 29 # Y
        )
    ])

def main():
    root = VarTk()
    root.title(_("Edit history test"))
    root.geometry("500x500")

    menubar = VarMenu(root)

    global hotkeys
    hotkeys = HotKey(root)

    editmenu = VarMenu(menubar, tearoff = False)
    editmenu.add_command(
        label = _("Undo"),
        command = undo,
        accelerator = hotkeys.get_keycode_string(undo)
    )
    editmenu.add_command(
        label = _("Redo"),
        command = redo,
        accelerator = hotkeys.get_keycode_string(redo)
    )
    menubar.add_cascade(label = _("Edit"), menu = editmenu)

    root.config(menu = menubar)

    root.after(5000, reg_hotkeys)

    root.grid()
    root.columnconfigure(0, weight = 1)
    root.rowconfigure(0, weight = 1)

    history = History()

    global tracker
    tracker = HistoryTracker(history)

    cnv = HistCanvasDnD(root, history_tracker = tracker)
    cnv.grid(row = 0, column = 0, sticky="NEWS")

    cnv.canvas.create_rectangle(
        10, 10, 100, 100,
        tags = "DnD",
        fill = "red"
    )

    root.mainloop()

if __name__ == '__main__':
    main()