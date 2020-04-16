#!/usr/bin/python

from examples import (
    Q35Project_2_6_0,
    Q35MachineNode_2_6_0
)
from widgets import (
    CoStatusView,
    GitVerSelDialog,
    QDCGUISignalHelper,
    DescNameWatcher,
    GUIPOp_SetBuildPath,
    Statusbar,
    GUIProjectHistoryTracker,
    HistoryWindow,
    askyesno,
    askopen,
    asksaveas,
    askdirectory,
    AddDescriptionDialog,
    GUIProject,
    HotKeyBinding,
    HotKey,
    ProjectWidget,
    VarMenu,
    GUITk
)
from argparse import (
    ArgumentParser
)
from qemu_device_creator import (
    arg_type_directory
)
from qemu import (
    QProject,
    qvd_get,
    BadBuildPath,
    MachineNode,
    load_build_path_list,
    account_build_path,
    QemuVersionDescription
)
from six.moves.tkinter import (
    NORMAL,
    DISABLED,
    END,
    IntVar
)
from six.moves.cPickle import (
    load as load_cPickled
)
from os import (
    remove
)
from common import (
    OrderedSet,
    Persistent,
    Variable,
    as_variable,
    FormatVar,
    execfile,
    CoSignal,
    CoTask,
    pythonize,
    mlget as _
)
from six.moves.tkinter import (
    RIGHT,
    BooleanVar,
    StringVar
)
from six.moves.tkinter_messagebox import (
    askyesnocancel,
    showinfo,
    showerror
)
import qdt

from traceback import (
    format_exception
)
import sys
from os.path import (
    join,
    isfile,
    expanduser
)


class ProjectGeneration(CoTask):
    def __init__(self, project, source_path, signal, reload_build_path_task,
        gen_chunk_graphs
    ):
        self.p = project
        self.s = source_path
        self.sig = signal
        self.finished = False
        self.reload_build_path_task = reload_build_path_task
        self.gen_chunk_graphs = gen_chunk_graphs
        CoTask.__init__(
            self,
            self.main(),
            description = _("Generation")
        )

    def main(self):
        try:
            yield self.reload_build_path_task
        except:
            self.prev_qvd = None # for `__finalize`
            raise RuntimeError("Cannot continue without a cache")

        cur_qvd = qvd_get(self.p.build_path, version = self.p.target_version)
        self.prev_qvd = cur_qvd.use()

        yield self.p.co_gen_all(self.s,
            known_targets = cur_qvd.qvc.known_targets,
            with_chunk_graph = self.gen_chunk_graphs
        )

    def on_failed(self):
        self.__finalize()

    def on_finished(self):
        showinfo(
            title = _("Generation completed").get(),
            message = _("No errors were reported.").get()
        )
        self.__finalize()

    def __finalize(self):
        if self.prev_qvd is not None:
            self.prev_qvd.use()
        self.finished = True
        self.sig.emit()

class QDCGUIWindow(GUITk, QDCGUISignalHelper):

    def __init__(self, project = None):
        GUITk.__init__(self, wait_msec = 1)

        for signame in [
            "qvc_dirtied",
            "qvd_failed",
            "qvc_available"
        ]:
            s = CoSignal()
            s.attach(self.signal_dispatcher)
            setattr(self, "sig_" + signame, s)

        self.title_suffix = _("Qemu device creator GUI")
        self.title_suffix.trace_variable("w", self.__on_title_suffix_write__)

        self.title_not_saved_asterisk = StringVar()
        self.title_not_saved_asterisk.trace_variable("w",
            self.__on_title_suffix_write__)
        self.saved_operation = None

        self.var_title = StringVar()
        self.title(self.var_title)

        # Hot keys, accelerators
        self.hk = hotkeys = HotKey(self)
        hotkeys.add_bindings([
            HotKeyBinding(
                self.invert_history_window,
                key_code = 43,
                description = _("If editing history window is hidden then \
show it else hide it."),
                symbol = "H"
            ),
            HotKeyBinding(
                self.on_load,
                key_code = 32,
                description = _("Load project from file."),
                symbol = "O"
            ),
            HotKeyBinding(
                self.on_new_project,
                key_code = 57,
                description = _("Create new project."),
                symbol = "N"
            ),
            HotKeyBinding(
                self.on_add_description,
                key_code = 40,
                description = _("Add description to the project"),
                symbol = "D"
            ),
            HotKeyBinding(
                self.on_set_qemu_build_path,
                key_code = 56,
                description = _("Set Qemu build path for the project"),
                symbol = "B"
            ),
            HotKeyBinding(
                self.on_sel_tgt_qemu_version,
                key_code = 28,
                description = _("Select target Qemu version for the project"),
                symbol = "T"
            ),
            HotKeyBinding(
                self.on_generate,
                key_code = 42,
                description = _("Launch code generation"),
                symbol = "G"
            ),
            HotKeyBinding(
                self.on_delete,
                key_code = 24,
                description = _("Shutdown the application."),
                symbol = "Q"
            ),
            HotKeyBinding(
                self.undo,
                key_code = 52,
                description = _("Revert previous editing."),
                symbol = "Z"
            ),
            HotKeyBinding(
                self.redo,
                key_code = 29,
                description = _("Make reverted editing again."),
                symbol = "Y"
            ),
            HotKeyBinding(
                self.on_save,
                key_code = 39,
                description = _("Save project."),
                symbol = "S"
            ),
            HotKeyBinding(
                self.on_reload,
                key_code = 27,
                description = _("Reload current project from file."),
                symbol = "R"
            )
        ])

        # see `set_user_settings`
        self._user_settings = None

        # Menu bar
        menubar = VarMenu(self)

        self.filemenu = filemenu = VarMenu(menubar, tearoff = False)
        filemenu.add_command(
            label = _("Add description"),
            command = self.on_add_description,
            accelerator = hotkeys.get_keycode_string(self.on_add_description)
        )
        filemenu.add_command(
            label = _("Set Qemu build path"),
            command = self.on_set_qemu_build_path,
            accelerator = hotkeys.get_keycode_string(
                self.on_set_qemu_build_path
            )
        )
        filemenu.add_command(
            label = _("Select target Qemu version"),
            command = self.on_sel_tgt_qemu_version,
            accelerator = hotkeys.get_keycode_string(
                self.on_sel_tgt_qemu_version
            )
        )
        filemenu.add_command(
            label = _("Generate"),
            command = self.on_generate,
            accelerator = hotkeys.get_keycode_string(
                self.on_generate
            )
        )
        filemenu.add_separator()
        filemenu.add_command(
            label = _("New project"),
            command = self.on_new_project,
            accelerator = hotkeys.get_keycode_string(self.on_new_project)
        ),
        filemenu.add_command(
            label = _("Save"),
            command = self.on_save,
            accelerator = hotkeys.get_keycode_string(self.on_save)
        ),
        filemenu.add_command(
            label = _("Save project as..."),
            command = self.on_save_as
        )
        filemenu.add_command(
            label = _("Load"),
            command = self.on_load,
            accelerator = hotkeys.get_keycode_string(self.on_load)
        ),
        self.reload_idx = filemenu.count
        filemenu.add_command(
            label = _("Reload"),
            command = self.on_reload,
            accelerator = hotkeys.get_keycode_string(self.on_reload)
        ),
        self.recentmenu = recentmenu = VarMenu(filemenu, tearoff = False)
        filemenu.add_cascade(
            label = _("Recent projects"),
            menu = recentmenu,
            state = DISABLED # a user settings instance is required
        )

        filemenu.add_separator()
        filemenu.add_command(
            label = _("Quit"),
            command = self.quit,
            accelerator = hotkeys.get_keycode_string(self.on_delete)
        )
        menubar.add_cascade(label = _("File"), menu = filemenu)

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

        editmenu.add_separator()

        editmenu.add_command(
            label = _("Rebuild Cache"),
            command = self.rebuild_cache,
            accelerator = hotkeys.get_keycode_string(self.rebuild_cache)
        )

        editmenu.add_separator()

        v = self.var_history_window = BooleanVar()
        v.set(False)

        self.__on_var_history_window = v.trace_variable("w",
            self.__on_var_history_window__
        )

        editmenu.add_checkbutton(
            label = _("Editing history window"),
            variable = v,
            accelerator = hotkeys.get_keycode_string(self.invert_history_window)
        )

        menubar.add_cascade(label = _("Edit"), menu = editmenu)

        self.optionsmenu = optionsmenu = VarMenu(menubar, tearoff = False)

        v = self.var_schedule_generation = BooleanVar()
        v.set(False)

        self.__on_var_schedule_generation = v.trace_variable("w",
            self.__on_var_schedule_generation__
        )

        optionsmenu.add_checkbutton(
            label = _("Schedule generation after cache loading"),
            variable = v
        )

        v = self.var_gen_chunk_graphs = BooleanVar()
        v.set(False)

        self.__on_var_gen_chunk_graphs = v.trace_variable("w",
            self.__on_var_gen_chunk_graphs__
        )

        optionsmenu.add_checkbutton(
            label = _("Generate chunk graphs"),
            variable = v
        )

        menubar.add_cascade(label = _("Options"), menu = optionsmenu)

        self.config(menu = menubar)

        # Widget layout
        self.grid()
        self.grid_columnconfigure(0, weight = 1)
        self.grid_rowconfigure(0, weight = 1)

        # Status bar
        self.grid_rowconfigure(1, weight = 0)
        self.sb = sb = Statusbar(self)
        sb.grid(row = 1, column = 0, sticky = "NEWS")

        # Target Qemu version in the status bar
        self._target_qemu = Variable(None)

        # This complicated scheme is required because the status must also
        # be updated on language change.
        @as_variable(self._target_qemu, _("No target"), _("Target Qemu: %s"))
        def var_target_qemu(target, no_target, target_qemu):
            if target is None:
                return no_target
            else:
                return target_qemu % target

        sb.left(var_target_qemu)

        # QEMU build path displaying
        self.var_qemu_build_path = StringVar()
        sb.left(self.var_qemu_build_path)

        # Task counters in status bar
        sb.right(_("Background tasks: "))
        sb.repack(CoStatusView(sb), RIGHT)

        self.signal_dispatcher.watch_failed(self.__on_listener_failed)

        self.protocol("WM_DELETE_WINDOW", self.on_delete)

        self.set_project(GUIProject() if project is None else project)

        self.__update_title__()
        self.__check_saved_asterisk__()

        self.qsig_watch("qvc_available", self.__on_qvc_available)

    def set_user_settings(self, val):
        if self._user_settings is val:
            return
        self._user_settings = val
        self._update_recent_projects()
        self._update_options()

    def _update_recent_projects(self):
        settings = self._user_settings
        menu = self.recentmenu

        # first, clear recent menu
        last = menu.index(END)
        if last is not None:
            menu.delete(0, last)

        added = 0
        if settings is not None:
            for f in reversed(list(settings.recent_projects)):
                # a simple check
                if not isfile(f):
                    settings.recent_projects.discard(f)
                    continue

                def do_load(file_name = f):
                    self._do_load(file_name)

                menu.add_command(label = f, command = do_load)

                added += 1

        self.filemenu.entryconfigure(
            self.filemenu.index(_("Recent projects").get()),
            state = NORMAL if added else DISABLED
        )

    def _update_options(self):
        settings = self._user_settings

        if settings is None:
            return

        self.var_schedule_generation.set(settings.schedule_generation)
        self.var_gen_chunk_graphs.set(settings.gen_chunk_graphs)

    def __on_listener_failed(self, e, tb):
        sys.stderr.write("Listener failed - %s" %
            "".join(format_exception(type(e), e, tb))
        )

    def __on_history_window_destroy__(self, *args, **kw):
        self.var_history_window.trace_vdelete("w",
            self.__on_var_history_window
        )

        self.var_history_window.set(False)

        self.__on_var_history_window = self.var_history_window.trace_variable(
            "w", self.__on_var_history_window__
        )

    def __on_var_history_window__(self, *args):
        if self.var_history_window.get():
            self._history_window = HistoryWindow(self.pht, self)
            self._history_window.bind("<Destroy>",
                self.__on_history_window_destroy__, "+"
            )
        else:
            try:
                self._history_window.destroy()
            except AttributeError:
                pass
            else:
                del self._history_window

    def invert_history_window(self):
        self.var_history_window.set(not self.var_history_window.get())

    def __on_var_schedule_generation__(self, *args):
        settings = self._user_settings

        if settings is not None:
            settings.schedule_generation = self.var_schedule_generation.get()

    def __on_var_gen_chunk_graphs__(self, *args):
        settings = self._user_settings

        if settings is not None:
            settings.gen_chunk_graphs = self.var_gen_chunk_graphs.get()

    def __on_title_suffix_write__(self, *args, **kw):
        self.__update_title__()

    def __update_title__(self):
        try:
            title_prefix = str(self.current_file_name)
        except AttributeError:
            title_prefix = "[New project]"

        self.var_title.set(
            title_prefix
                + self.title_not_saved_asterisk.get()
                + " - "
                + self.title_suffix.get()
        )

    def check_undo_redo(self):
        can_do = self.pht.can_do()

        self.hk.set_enabled(self.redo, can_do)
        if can_do:
            self.editmenu.entryconfig(self.redo_idx, state = NORMAL)
        else:
            self.editmenu.entryconfig(self.redo_idx, state = DISABLED)

        can_undo = self.pht.can_undo()

        self.hk.set_enabled(self.undo, can_undo)
        if can_undo:
            self.editmenu.entryconfig(self.undo_idx, state = NORMAL)
        else:
            self.editmenu.entryconfig(self.undo_idx, state = DISABLED)

    def set_current_file_name(self, file_name = None):
        if file_name is None:
            try:
                del self.current_file_name
            except AttributeError:
                pass # already deleted
            else:
                self.filemenu.entryconfig(self.reload_idx, state = DISABLED)
        else:
            # TODO: watch the file in FS and auto ask user to reload
            self.current_file_name = file_name
            self.filemenu.entryconfig(self.reload_idx, state = NORMAL)

        self.__update_title__()

    def set_project(self, project):
        try:
            pht = self.pht
        except AttributeError:
            # Project was never been set
            pass
        else:
            pht.unwatch_changed(self.on_changed)

        try:
            self.pw.destroy()
        except AttributeError:
            # project widget was never been created
            pass

        # Close history window
        if self.var_history_window.get():
            self.var_history_window.set(False)

        self.proj = project
        self.pht = GUIProjectHistoryTracker(self.proj, self.proj.history)

        DescNameWatcher(self.pht)

        self.pw = ProjectWidget(self.proj, self)
        self.pw.grid(column = 0, row = 0, sticky = "NEWS")

        self.update_qemu_build_path(project.build_path)
        self.update_target_qemu()

        self.pht.watch_changed(self.on_changed)
        self.check_undo_redo()

    def __saved_asterisk__(self, saved = True):
        if saved:
            if self.title_not_saved_asterisk.get() != "":
                self.title_not_saved_asterisk.set("")
        else:
            if self.title_not_saved_asterisk.get() != "*":
                self.title_not_saved_asterisk.set("*")

    def __check_saved_asterisk__(self):
        if self.saved_operation == self.pht.pos:
            self.__saved_asterisk__(True)
        else:
            self.__saved_asterisk__(False)

    def on_changed(self, op, *args, **kw):
        self.check_undo_redo()
        self.__check_saved_asterisk__()

        if isinstance(op, GUIPOp_SetBuildPath):
            proj = self.proj
            if op.p is proj:
                self.update_qemu_build_path(proj.build_path)
                # Note that target Qemu version info will be update when QVC
                # will be ready.

    def undo(self):
        self.pht.undo_sequence()

    def redo(self):
        self.pht.do_sequence()

    def rebuild_cache(self):
        try:
            qvd = qvd_get(self.proj.build_path,
                version = self.proj.target_version
            )
        except BadBuildPath as e:
            showerror(
                title = _("Cache rebuilding is impossible").get(),
                message = (_("Selected Qemu build path is bad. Reason: %s") % (
                    e.message
                )).get()
            )
            return

        # if 'reload_build_path_task' is not failed
        if hasattr(self.pw, 'reload_build_path_task'):
            # reload_build_path_task always run at program start that is why
            # it's in process when it's not in finished_tasks and not failed
            if self.pw.reload_build_path_task not in self.pw.tm.finished_tasks:
                ans = askyesno(self,
                    title = _("Cache rebuilding"),
                    message = _("Cache building is already \
in process. Do you want to start cache rebuilding?")
                )
                if not ans:
                    return

        qvd.remove_cache()
        self.pw.reload_build_path()

    def on_delete(self):
        if self.title_not_saved_asterisk.get() == "*":
            resp = askyesnocancel(
                title = self.title_suffix.get(),
                message = _(
                    "Current project has unsaved changes."
                    " Would you like to save it?"
                    "\n\nNote that a backup is always saved with name"
                    " project.py in current working directory."
                ).get()
            )
            if resp is None:
                return
            if resp:
                self.on_save()

                if self.title_not_saved_asterisk.get() == "*":
                    # user canceled saving during on_save
                    return

        try:
            """ TODO: Note that it is possible to prevent window to close if a
            generation task is in process. But is it really needed? """

            self.task_manager.remove(self._project_generation_task)
        except AttributeError:
            pass
        else:
            del self._project_generation_task

        self.signal_dispatcher.unwatch_failed(self.__on_listener_failed)

        self.quit()

    def on_add_description(self):
        d = AddDescriptionDialog(self.pht, self)

    def on_set_qemu_build_path(self):
        dir = askdirectory(self, title = _("Select Qemu build path"))
        if not dir:
            return

        self.pht.set_build_path(dir)

    def on_sel_tgt_qemu_version(self):
        try:
            qvd = qvd_get(self.proj.build_path)
        except:
            repo = None
        else:
            repo = qvd.repo

        new_target = GitVerSelDialog(self, repo).wait()

        if new_target is None:
            return

        self.pht.set_target(new_target)

    def on_generate(self):
        try:
            t = self._project_generation_task
        except AttributeError:
            pass
        else:
            if not t.finished:
                showerror(
                    title = _("Generation is cancelled").get(),
                    message = _("At least one generation task is already \
in process.").get()
                )
                return

        if not self.proj.build_path:
            showerror(
                title = _("Generation is impossible").get(),
                message = _("No Qemu build path is set for the project.").get()
            )
            return

        try:
            qvd = qvd_get(self.proj.build_path,
                version = self.proj.target_version
            )
        except BadBuildPath as e:
            showerror(
                title = _("Generation is impossible").get(),
                message = (_("Selected Qemu build path is bad. Reason: %s") % (
                    e.message
                )).get()
            )
            return

        if not hasattr(self.pw, "reload_build_path_task"):
            showerror(
                title = _("Generation is impossible").get(),
                message = _("Qemu version cache loading failed.").get()
            )
            return

        if not qvd.qvc_is_ready and not self.var_schedule_generation.get():
            showerror(
                title = _("Generation is cancelled").get(),
                message = _("Qemu version cache is not ready yet. Try \
later.").get()
            )
            return

        self._project_generation_task = ProjectGeneration(
            self.proj,
            qvd.src_path,
            self.sig_qvc_dirtied,
            self.pw.reload_build_path_task,
            self.var_gen_chunk_graphs.get()
        )
        self.task_manager.enqueue(self._project_generation_task)

    def load_project_from_file(self, file_name):
        loaded_variables = dict(qdt.__dict__)

        try:
            execfile(file_name, loaded_variables)
        except Exception as e:
            raise e
        else:
            qproj = None
            for v in loaded_variables.values():
                if isinstance(v, GUIProject):
                    break
                elif qproj is None and isinstance(v, QProject):
                    qproj = v
            else:
                if qproj:
                    v = GUIProject.from_qproject(qproj)
                else:
                    raise Exception("No project object was loaded")

            self.set_project(v)
            self.set_current_file_name(file_name)
            self.saved_operation = self.pht.pos
            self.__check_saved_asterisk__()

            if self._user_settings:
                self._user_settings.account_project(file_name)
                self._update_recent_projects()

    def save_project_to_file(self, file_name):
        self.pw.refresh_layouts()

        project = self.proj

        # Ensure that all machine nodes are in corresponding lists
        for d in project.descriptions:
            if isinstance(d, MachineNode):
                d.link(handle_system_bus = False)

        pythonize(project, file_name)

        self.set_current_file_name(file_name)
        self.saved_operation = self.pht.pos
        self.__check_saved_asterisk__()

    def try_save_project_to_file(self, file_name):
        try:
            open(file_name, "wb").close()
        except IOError as e:
            if not e.errno == 13: # Do not remove read-only files
                try:
                    remove(file_name)
                except:
                    pass

            showerror(
                title = _("Cannot save project").get(),
                message = str(e)
            )
            return

        self.save_project_to_file(file_name)

        if self._user_settings:
            self._user_settings.account_project(file_name)
            self._update_recent_projects()

    def on_save_as(self):
        fname = asksaveas(self,
            [(_("QDC GUI Project defining script"), ".py")],
            title = _("Save project")
        )

        if not fname:
            return

        self.try_save_project_to_file(fname)

    def on_save(self):
        try:
            fname = self.current_file_name
        except AttributeError:
            self.on_save_as()
        else:
            self.try_save_project_to_file(fname)

    def check_unsaved(self):
        if self.title_not_saved_asterisk.get() == "*":
            return askyesno(self,
                title = self.title_suffix,
                message =
_("Current project has unsaved changes. They will be lost. Continue?")
            )
        else:
            return True

    def on_new_project(self):
        if not self.check_unsaved():
            return

        self.set_project(GUIProject())
        self.set_current_file_name()

        """ There is nothing to save in just created project. So declare that
all changes are saved. """  
        self.saved_operation = self.pht.pos
        self.__check_saved_asterisk__()

    def on_load(self):
        if not self.check_unsaved():
            return

        fname = askopen(self, [(_("QDC GUI Project defining script"), ".py")],
            title = _("Load project")
        )

        if fname:
            self._do_load(fname)

    def _do_load(self, fname):
        try:
            self.load_project_from_file(fname)
        except Exception as e:
            showerror(
                title = _("Project loading failed").get(),
                message = str(e)
            )

    def on_reload(self):
        try:
            fname = self.current_file_name
        except AttributeError:
            # No file is selected for the project yet
            return

        if not self.check_unsaved():
            return

        self._do_load(fname)

    def update_qemu_build_path(self, bp):
        if bp is None:
            self.var_qemu_build_path.set(_("No QEMU build path selected").get())
        else:
            self.var_qemu_build_path.set("QEMU: " + bp)

    def update_target_qemu(self):
        p, qvd = self.proj, QemuVersionDescription.current
        self._target_qemu.set(p and p.target_version or qvd and qvd.commit_sha)

    def __on_qvc_available(self):
        self.update_target_qemu()


class Settings(Persistent):
    "Keeps user settings in a file."

    def __init__(self, file_name):
        super(Settings, self).__init__(file_name,
            glob = globals(),
            version = 1.0,
            # default values
            schedule_generation = False,
            gen_chunk_graphs = False,
            recent_projects = OrderedSet()
        )

    def account_project(self, file_name):
        # re-add file name to preserve recent order
        if file_name in self.recent_projects:
            self.recent_projects.discard(file_name)
        self.recent_projects.add(file_name)


def main():
    parser = ArgumentParser()

    parser.add_argument(
        '--qemu-build', '-b',
        default = None,
        type = arg_type_directory,
        metavar = 'path_to_qemu_build',
        )

    parser.add_argument("script",
        default = "project.py",
        nargs = "?",
        help = "Load project from a script."
    )

    arguments = parser.parse_args()

    root = QDCGUIWindow()

    try:
        root.load_project_from_file(arguments.script)
    except Exception as e:
        print("Project load failed: " + str(e) + "\n")

        project = GUIProject()

        try:
            variables = {}
            execfile("serialize-test.py", qdt.__dict__, variables)
    
            for v in variables.values():
                if isinstance(v, MachineNode):
                    mach = v
                    break
            else:
                raise Exception(
                    "No MachineNode instance was found in serialize-test.py")
        except Exception as e:
            print("Machine load failed: " + str(e) + "\n")
            mach = Q35MachineNode_2_6_0()

        project.add_description(mach)

        try:
            layout = load_cPickled(open("layout.p", "rb"))
        except Exception as e:
            print("Layout load failed: " + str(e) + "\n")
        else:
            project.layouts.append((mach.name, layout))

        tmp_p = Q35Project_2_6_0()
        for desc in list(tmp_p.descriptions):
            if not isinstance(desc, MachineNode):
                desc.remove_from_project()
                project.add_description(desc)

        root.set_project(project)
        root.set_current_file_name("project.py")

    if arguments.qemu_build is not None:
        load_build_path_list()
        account_build_path(arguments.qemu_build)
        root.pht.set_build_path(arguments.qemu_build)

    with Settings(expanduser(join("~", ".qdt.py"))) as settings:
        root.set_user_settings(settings)

        root.geometry("1000x750")

        root.mainloop()

    root.save_project_to_file("project.py")

if __name__ == '__main__':
    main()
