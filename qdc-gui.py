#!/usr/bin/python2

from examples import \
    Q35Project_2_6_0, \
    Q35MachineNode_2_6_0

from widgets import \
    AddDescriptionDialog, \
    __dict__ as widgets_dict, \
    GUIProject, \
    HotKeyBinding, \
    HotKey, \
    ProjectWidget, \
    VarMenu, \
    VarTk

import cPickle
import qemu

from common import \
    PyGenerator, \
    ML as _

class QDCGUIWindow(VarTk):
    def __init__(self, project):
        VarTk.__init__(self)

        self.proj = project

        self.title(_("Qemu device creator GUI"))

        # Hot keys, accelerators
        self.hk = hotkeys = HotKey(self)
        hotkeys.add_bindings([
            HotKeyBinding(
                self.on_add_description,
                key_code = 40, # D
                description = _("Add description to the project")
            ),
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
            label = _("Add description"),
            command = self.on_add_description,
            accelerator = hotkeys.get_keycode_string(self.on_add_description)
        )
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

        self.pw = ProjectWidget(self.proj, self)
        self.pw.grid(column = 0, row = 0, sticky = "NEWS")

        self.proj.pht.add_on_changed(self.on_changed)
        self.chack_undo_redo()

        self.protocol("WM_DELETE_WINDOW", self.on_delete)

    def chack_undo_redo(self):
        can_do = self.proj.pht.can_do()

        self.hk.set_enabled(self.redo, can_do)
        if can_do:
            self.editmenu.entryconfig(self.redo_idx, state = "normal")
        else:
            self.editmenu.entryconfig(self.redo_idx, state = "disabled")

        can_undo = self.proj.pht.can_undo()

        self.hk.set_enabled(self.undo, can_undo)
        if can_undo:
            self.editmenu.entryconfig(self.undo_idx, state = "normal")
        else:
            self.editmenu.entryconfig(self.undo_idx, state = "disabled")

    def on_changed(self, *args, **kw):
        self.chack_undo_redo()

    def undo(self):
        self.pw.undo()

    def redo(self):
        self.pw.redo()

    def on_delete(self):
        self.quit()

    def on_add_description(self):
        d = AddDescriptionDialog(self.proj.pht, self)

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

        project.add_description(mach)

    try:
        layout = project.get_layouts(mach.name)[0]
    except IndexError:
        try:
            layout = cPickle.load(open("layout.p", "rb"))
        except Exception, e:
            print "Layout load filed: " + str(e) + "\n"
            layout = {}
        project.layouts = [(mach.name, layout)]

    for desc in project.descriptions:
        if not isinstance(desc, qemu.MachineNode):
            break
    else:
        tmp_p = Q35Project_2_6_0()
        for desc in list(tmp_p.descriptions):
            if not isinstance(desc, qemu.MachineNode):
                desc.remove_from_project()
                project.add_description(desc)

    root = QDCGUIWindow(project)
    root.geometry("1000x750")

    root.mainloop()

    root.pw.refresh_layouts()

    PyGenerator().serialize(open("project.py", "wb"), project)

if __name__ == '__main__':
    main()