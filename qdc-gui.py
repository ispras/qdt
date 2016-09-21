#!/usr/bin/python2

from examples import \
    Q35MachineNode_2_6_0

from widgets import \
    __dict__ as widgets_dict, \
    GUIProject, \
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

        self.mw = MachineWidget(self.mach, self)
        self.mw.grid(column = 0, row = 0, sticky = "NEWS")

        self.mw.mdw.mht.add_on_changed(self.on_changed)
        self.chack_undo_redo()

        self.protocol("WM_DELETE_WINDOW", self.on_delete)

        self.on_enter_main_loop_id = self.after(0, self.on_enter_main_loop)

    def chack_undo_redo(self):
        can_do = self.mw.mdw.mht.can_do()

        self.hk.set_enabled(self.redo, can_do)
        if can_do:
            self.editmenu.entryconfig(self.redo_idx, state = "normal")
        else:
            self.editmenu.entryconfig(self.redo_idx, state = "disabled")

        can_undo = self.mw.mdw.mht.can_undo()

        self.hk.set_enabled(self.undo, can_undo)
        if can_undo:
            self.editmenu.entryconfig(self.undo_idx, state = "normal")
        else:
            self.editmenu.entryconfig(self.undo_idx, state = "disabled")

    def on_changed(self, *args, **kw):
        self.chack_undo_redo()

    def undo(self):
        self.mw.mdw.mht.undo()

    def redo(self):
        self.mw.mdw.mht.do()

    def on_enter_main_loop(self):
        self.on_enter_main_loop_id = None

        self.mw.mdw.ph_run()

    def set_machine_widget_layout(self, layout):
        self.mw.mdw.SetLayout(layout)

    def get_machine_widget_layout(self):
        return self.mw.mdw.GetLayout()

    def on_delete(self):
        if not self.on_enter_main_loop_id is None:
            self.after_cancel(self.on_enter_main_loop_id)

        self.quit()

def main():
    try:
        variables = {}
        context = dict(qemu.__dict__)
        context.update(widgets_dict)
        execfile("project.py", context, variables)

        for v in variables.values():
            if isinstance(v, GUIProject):
                project = v
                break
    except Exception, e:
        print "Project load filed: " + str(e) + "\n"
        project = GUIProject()

    try:
        mach = project.get_machine_descriptions()[0]
    except IndexError:
        try:
            variables = {}
            execfile("serialize-test.py", qemu.__dict__, variables)
    
            for v in variables.values():
                if isinstance(v, qemu.MachineNode):
                    mach = v
                    break
        except Exception, e:
            print "Machine load failed: " + str(e) + "\n"
            mach = Q35MachineNode_2_6_0()

        project.descriptions.append(mach)

    try:
        layout = project.get_layouts(mach.name)[0]
    except IndexError:
        try:
            layout = cPickle.load(open("layout.p", "rb"))
        except Exception, e:
            print "Layout load filed: " + str(e) + "\n"
            layout = {}
        project.layouts = [(mach.name, layout)]

    root = QDCGUIWindow(mach)
    root.geometry("1000x750")
    root.set_machine_widget_layout(layout)

    root.mainloop()

    project.layouts = [(mach.name, layout)]

    PyGenerator().serialize(open("project.py", "wb"), project)

if __name__ == '__main__':
    main()