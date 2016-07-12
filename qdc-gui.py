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

def main():
    root = VarTk()
    root.title(_("Qemu device creator GUI"))

    root.grid()
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)
    root.geometry("500x500")

    hotkeys = HotKey(root)
    hotkeys.add_bindings([
        HotKeyBinding(
            root.quit,
            key_code = 24, # Q
            description = _("Shutdown the application.")
        )
    ])

    menubar = VarMenu(root)

    filemenu = VarMenu(menubar, tearoff = False)
    filemenu.add_command(
        label=_("Quit"),
        command = root.quit,
        accelerator = hotkeys.get_keycode_string(root.quit)
    )
    menubar.add_cascade(label=_("File"), menu = filemenu)

    root.config(menu = menubar)

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

    cnv = MachineWidget(root, mach)

    try:
        layout = cPickle.load(open("layout.p", "rb"))
    except:
        layout = {}

    cnv.SetLyout(layout)

    cnv.grid(column = 0, row = 0, sticky = "NEWS")

    cnv.ph_run()

    root.mainloop()

    layout = cnv.GetLayout()
    cPickle.dump(layout, open("layout.p", "wb"))

    with open("serialize-test.py", "wb") as f:
        PyGenerator().serialize(f, mach)
        f.close()

if __name__ == '__main__':
    main()