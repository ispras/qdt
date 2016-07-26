#!/usr/bin/python2

from examples import \
    Q35MachineNode_2_6_0

from widgets import \
    HotKeyBinding, \
    HotKey, \
    MachineWidget, \
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
    
        self.config(menu = menubar)

        # Widget layout
        self.grid()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.mw = MachineWidget(self, self.mach)
        self.mw.grid(column = 0, row = 0, sticky = "NEWS")

        self.protocol("WM_DELETE_WINDOW", self.on_delete)

        self.on_enter_main_loop_id = self.after(0, self.on_enter_main_loop)

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