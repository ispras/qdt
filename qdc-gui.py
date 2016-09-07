#!/usr/bin/python2

from examples import \
    Q35MachineNode_2_6_0

from widgets import \
    HotKeyBinding, \
    HotKey, \
    MachineDiagramWidget, \
    VarMenu, \
    VarTk

import cPickle
import qemu

from common import \
    PyGenerator, \
    ML as _

class QDCGUIWindow(VarTk):
    def __init__(self, machine_description):
        VarTk.__init__(self)

        self.mach = machine_description

        self.title(_("Qemu device creator GUI"))

        # Hot keys, accelerators
        self.hk = hotkeys = HotKey(self)
        hotkeys.add_bindings([
            HotKeyBinding(
                self.on_delete,
                key_code = 24, # Q
                description = _("Shutdown the application.")
            ),
            HotKeyBinding(
                self.undo,
                key_code = 52, # Z
                description = _("Revert previous editing.")
            ),
            HotKeyBinding(
                self.redo,
                key_code = 29, # Y
                description = _("Make reverted editing again.")
            )
        ])

        # Menu bar
        menubar = VarMenu(self)

        filemenu = VarMenu(menubar, tearoff = False)
        filemenu.add_command(
            label=_("Quit"),
            command = self.quit,
            accelerator = hotkeys.get_keycode_string(self.on_delete)
        )
        menubar.add_cascade(label=_("File"), menu = filemenu)

        self.editmenu = editmenu = VarMenu(menubar, tearoff = False)
        editmenu.add_command(
            label = _("Undo"),
            command = self.undo,
            accelerator = hotkeys.get_keycode_string(self.undo)
        )
        self.undo_idx = editmenu.count - 1

        editmenu.add_command(
            label = _("Redo"),
            command = self.redo,
            accelerator = hotkeys.get_keycode_string(self.redo)
        )
        self.redo_idx = editmenu.count - 1

        menubar.add_cascade(label = _("Edit"), menu = editmenu)

        self.config(menu = menubar)

        # Widget layout
        self.grid()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.mw = MachineDiagramWidget(self, self.mach)
        self.mw.grid(column = 0, row = 0, sticky = "NEWS")

        self.mw.mht.add_on_changed(self.on_changed)
        self.chack_undo_redo()

        self.protocol("WM_DELETE_WINDOW", self.on_delete)

        self.on_enter_main_loop_id = self.after(0, self.on_enter_main_loop)

    def chack_undo_redo(self):
        can_do = self.mw.mht.can_do()

        self.hk.set_enabled(self.redo, can_do)
        if can_do:
            self.editmenu.entryconfig(self.redo_idx, state = "normal")
        else:
            self.editmenu.entryconfig(self.redo_idx, state = "disabled")

        can_undo = self.mw.mht.can_undo()

        self.hk.set_enabled(self.undo, can_undo)
        if can_undo:
            self.editmenu.entryconfig(self.undo_idx, state = "normal")
        else:
            self.editmenu.entryconfig(self.undo_idx, state = "disabled")

    def on_changed(self, *args, **kw):
        self.chack_undo_redo()

    def undo(self):
        self.mw.mht.undo()

    def redo(self):
        self.mw.mht.do()

    def on_enter_main_loop(self):
        self.on_enter_main_loop_id = None

        self.mw.ph_run()

    def set_machine_widget_layout(self, layout):
        self.mw.SetLayout(layout)

    def get_machine_widget_layout(self):
        return self.mw.GetLayout()

    def on_delete(self):
        if not self.on_enter_main_loop_id is None:
            self.after_cancel(self.on_enter_main_loop_id)

        self.quit()

def main():
    mach = None
    try:
        variables = {}
        execfile("serialize-test.py", qemu.__dict__, variables)

        for v in variables.values():
            if isinstance(v, qemu.MachineNode):
                mach = v
                break
    except Exception, e:
        print "Machine load failed: " + str(e) + "\n"

    if not mach:
        mach = Q35MachineNode_2_6_0()

    root = QDCGUIWindow(mach)
    root.geometry("500x500")

    try:
        layout = cPickle.load(open("layout.p", "rb"))
    except:
        layout = {}

    root.set_machine_widget_layout(layout)

    root.mainloop()

    layout = root.get_machine_widget_layout()
    cPickle.dump(layout, open("layout.p", "wb"))

    with open("serialize-test.py", "wb") as f:
        PyGenerator().serialize(f, mach)
        f.close()

if __name__ == '__main__':
    main()