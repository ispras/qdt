#!/usr/bin/python

from common import (
    QRepo,
    makedirs,
    bidict,
    mlget as _,
    Persistent
)
from os.path import (
    exists,
    dirname,
    join,
    expanduser
)
from widgets import (
    Statusbar,
    CoStatusView,
    ErrorDialog,
    GUIFrame,
    GitVerSelWidget,
    VarButton,
    HKEntry,
    VarLabel,
    GUIDialog,
    askdirectory,
    VarNotebook,
    askyesno,
    HotKey,
    ErrorDialog,
    askdirectory,
    add_scrollbars_native,
    VarTreeview,
    MenuBuilder,
    GUITk
)
from six.moves.tkinter import (
    RIGHT,
    StringVar,
    Label,
    END
)
from traceback import (
    format_exc
)


class QMSettings(Persistent):

    def __init__(self, file_name):
        super(QMSettings, self).__init__(file_name,
            glob = globals(),
            version = 0.1,
            # default values
            repo_paths = [],
            geometry = "800x600"
        )


def main():
    settings_file = expanduser(join("~", ".qmanager.py"))
    print("Reading settings from " + settings_file)
    with QMSettings(settings_file) as settings:
        start_gui(settings)


def start_gui(settings):
    repos = []
    for path in settings.repo_paths:
        try:
            r = QRepo(path)
        except:
            continue
        repos.append(r)

    root = QMGUI(repos)
    root.geometry(settings.geometry + "+" + root.geometry().split("+", 1)[1])
    root.mainloop()
    settings.geometry = root.last_geometry

    settings.repo_paths = list(r.path for r in root.repos)


class QMGUI(GUITk):

    def __init__(self, repos):
        GUITk.__init__(self)
        self.title(_("QManager"))

        self.hk = hotkeys = HotKey(self)
        hotkeys(self._on_account_git_repo, 38, symbol = "A")
        hotkeys(self._on_forget_repo, 41, symbol = "F")
        hotkeys(self._on_copy_path, 54, symbol = "C")
        hotkeys(self._on_create_worktree, 25, symbol = "W")
        hotkeys(self._on_create_build_dir, 56, symbol = "B")

        with MenuBuilder(self) as menubar:
            with menubar(_("Manage")) as repomenu:
                repomenu(_("Account Git repository"),
                    command = self._on_account_git_repo,
                    accelerator = hotkeys.get_keycode_string(
                        self._on_account_git_repo
                    )
                )
                repomenu(_("Forget repository"),
                    command = self._on_forget_repo,
                    accelerator = hotkeys.get_keycode_string(
                        self._on_forget_repo
                    )
                )
                repomenu()
                repomenu(_("Create work tree"),
                    command = self._on_create_worktree,
                    accelerator = hotkeys.get_keycode_string(
                        self._on_create_worktree
                    )
                )
                repomenu(_("Delete work tree"),
                    command = self._on_delete_worktree,
                )
                repomenu()
                repomenu(_("Exit"),
                    command = self._on_exit
                )
            with menubar(_("Work tree")) as wtmenu:
                wtmenu(_("Create build directory"),
                    command = self._on_create_build_dir,
                    accelerator = hotkeys.get_keycode_string(
                        self._on_create_build_dir
                    )
                )
            with menubar(_("Help")) as helpmenu:
                helpmenu(_("About"),
                    command = self._on_about
                )

        self.protocol("WM_DELETE_WINDOW", self._on_exit)

        self.tv_repos = tv_repos = VarTreeview(self,
            columns = ("HEAD", "SHA1")
        )

        self.columnconfigure(0, weight = 1)

        row = 0

        self.rowconfigure(row, weight = 1)
        tv_repos.grid(row = row, column = 0, sticky = "NESW")

        add_scrollbars_native(self, tv_repos, row = row, sizegrip = True)
        row += 1 # horizontal scrollbar

        tv_repos.heading("#0", text =  _("Path"))
        tv_repos.heading("HEAD", text =  _("HEAD"))
        tv_repos.heading("SHA1", text =  _("SHA1"))

        self.repo2iid = repo2iid = bidict()
        self.iid2repo = repo2iid.mirror

        self.worktree2iid = worktree2iid = bidict()
        self.iid2worktree = worktree2iid.mirror

        # status bar
        row += 1; self.rowconfigure(row, weight = 0)
        sb = Statusbar(self)
        sb.grid(row = row, column = 0, columnspan = 2, sticky = "SEW")

        sb.right(_("Background tasks: "))
        sb.repack(CoStatusView(sb), RIGHT)

        self.repos = []
        for r in repos:
            self._account_repo(r)

    def _worktree_by_iid(self, iid):
        try:
            # likely
            return self.iid2worktree[iid]
        except KeyError:
            qrepo = self.iid2repo[iid]
            # one of work trees is the repo
            return qrepo.worktrees[qrepo.path]

    def _on_create_build_dir(self):
        sel = self.tv_repos.selection()

        for r in set(self._worktree_by_iid(iid) for iid in sel):
            res = BuildDirCreationDialog(self, r).wait()
            if not res:
                continue

            self._create_build_dir(*res)

    def _create_build_dir(self, qwt, directory, options):
        while True:
            try:
                makedirs(directory, exist_ok = True)
            except:
                ErrorDialog(
                    summary = _("Check build directory creation options"),
                    message = format_exc()
                ).wait()
                # allow user to correct settings
                dlg = BuildDirCreationDialog(self, qwt, directory, **options)
                res = dlg.wait()
                if res is None:
                    break
                qwt, directory, options = res
                continue
            break

    def _qrepo_by_iid(self, iid):
        try:
            # likely
            return self.iid2worktree[iid].qrepo
        except KeyError:
            return self.iid2repo[iid]

    def _on_create_worktree(self):
        sel = self.tv_repos.selection()

        for r in set(self._qrepo_by_iid(iid) for iid in sel):
            res = WorkTreeCreationDialog(self, r).wait()
            if not res:
                continue

            self.task_manager.enqueue(self._co_create_worktree(*res))

    def _co_create_worktree(self, qrepo, directory, options):
        while True:
            try:
                yield qrepo.co_create_worktree(directory,
                    callback = self._on_worktree,
                    **options
                )
            except:
                ErrorDialog(
                    summary = _("Check work tree creation options"),
                    message = format_exc()
                ).wait()
                # allow user to correct settings
                dlg = WorkTreeCreationDialog(self, qrepo, directory, **options)
                res = dlg.wait()
                if res is None:
                    break
                qrepo, directory, options = res
                continue
            break

    def _on_delete_worktree(self):
        sel = self.tv_repos.selection()

        for wt in set(self._worktree_by_iid(iid) for iid in sel):
            if wt.build_dirs:
                ErrorDialog(_("Cannot remove work tree"),
                    summary = _("%s has build directories.") % wt.path
                ).wait()
                continue

    def _on_worktree(self, wt):
        r2i, w2i = self.repo2iid, self.worktree2iid

        w2i[wt] = self.tv_repos.insert(r2i[wt.qrepo], END,
            text = wt,
            open = True,
            values = _repo_column_values(wt.repo)
        )

    def _on_copy_path(self):
        tv = self.tv_repos
        sel = tv.selection()
        if not sel:
            return

        item = tv.item

        # Path of only first selected item is copied to clipboard.
        text = item(sel[0], "text")

        self.clipboard_clear()
        self.clipboard_append(text)

    def _account_repo(self, r):
        self.task_manager.enqueue(self._co_account_repo(r))

    def _co_account_repo(self, r):
        select = not self.repos # auto select first accounted repo

        self.repos.append(r)
        self.repo2iid[r] = self.tv_repos.insert("", END,
            text = r,
            open = True,
            values = _repo_column_values(r.repo)
        )

        if select:
            self.tv_repos.selection_set(self.repo2iid[r])

        yield r.co_prune()
        yield r.co_get_worktrees(self._on_worktree)

    def _forget_repo(self, r):
        self.repos.remove(r)
        iid = self.repo2iid.pop(r)
        self.tv_repos.delete(iid)
        for wt in r.worktrees.values():
            del self.worktree2iid[wt]

    def _on_forget_repo(self):
        sel = self.tv_repos.selection()
        if not sel:
            return

        to_forget = set(self._qrepo_by_iid(iid) for iid in sel)

        if not askyesno(self, _("Forget those repositories?"),
            _("%s") % "\n".join(r.path for r in to_forget)
        ):
            return

        for r in to_forget:
            self._forget_repo(r)

    def _on_account_git_repo(self):
        path = askdirectory(self, title = _("Select Git repository"))
        if not path:
            return

        try:
            r = QRepo(path)
        except:
            ErrorDialog(_("Bad path selected"), message = format_exc())
            return

        self._account_repo(r)

    def _on_about(self):
        print("About")

    def _on_exit(self):
        self.last_geometry = self.geometry().split("+", 1)[0]
        self.destroy()


def _repo_column_values(repo):
    head = repo.head
    return (
        _("[detached]") if head.is_detached else head.reference.name,
        head.commit.hexsha
    )


class WorkTreeCreationDialog(GUIDialog):

    def __init__(self, master,
        # Keep those args with sync with result (see _on_create_worktree)
        qrepo,
        init_directory = "",
        new_branch = "",
        version = None,
        **kw
    ):
        GUIDialog.__init__(self, master, **kw)
        self.qrepo = qrepo

        self.title(_("Work tree creation"))

        self.columnconfigure(0, weight = 0)
        self.columnconfigure(1, weight = 1)
        self.columnconfigure(2, weight = 0)

        row = 0
        # Main: path to base repo
        self.rowconfigure(row, weight = 0)
        VarLabel(self, text = _("Main:")).grid(
            row = row,
            column = 0,
            sticky = "E"
        )
        Label(self, text = qrepo.path).grid(
            row = row,
            column = 1,
            sticky = "W",
            columnspan = 2
        )

        # Work tree: path to new work tree, Browse
        row += 1; self.rowconfigure(row, weight = 0)
        VarLabel(self, text = _("Work tree:")).grid(
            row = row,
            column = 0,
            sticky = "E"
        )
        self.var_worktree = StringVar(value = init_directory)
        HKEntry(self, textvariable = self.var_worktree, width = 100).grid(
            row = row, column = 1, sticky = "NESW"
        )
        VarButton(self, text = _("Browse"), command = self._on_browse_wt).grid(
            row = row, column = 2
        )

        # Version: version selection
        row += 1; self.rowconfigure(row, weight = 0)
        VarLabel(self, text = _("Base version:")).grid(
            row = row,
            column = 0,
            sticky = "E"
        )
        self.git_ver_sel_widget = w = GitVerSelWidget(self, qrepo.repo)
        if version is not None:
            w.selected.set(version)
        w.grid(row = row, column = 1, columnspan = 2, sticky = "NESW")

        # New branch
        row += 1; self.rowconfigure(row, weight = 0)
        VarLabel(self, text = _("New branch:")).grid(
            row = row,
            column = 0,
            sticky = "E"
        )
        self.var_new_branch = StringVar(
            value = new_branch
        )
        HKEntry(self, textvariable = self.var_new_branch, width = 100).grid(
            row = row, column = 1, columnspan = 2, sticky = "NESW"
        )

        # Buttons
        row += 1; self.rowconfigure(row, weight = 0)
        bt_frame = GUIFrame(self)
        bt_frame.grid(row = row, column = 0, columnspan = 3, sticky = "NES")

        VarButton(bt_frame,
            text = _("Create"),
            command = self._on_create_worktree
        ).pack()

    def _on_browse_wt(self):
        cur = self.var_worktree.get()
        self.var_worktree.set(
            askdirectory(self,
                title = _("Select work tree"),
                # we want to suggest a directory near base repository
                initialdir = cur or dirname(self.qrepo.path)
            )
            or cur
        )

    def _on_create_worktree(self):
        directory = self.var_worktree.get()
        if not directory:
            ErrorDialog(summary = _("Select work tree"))
            return

        if exists(directory):
            if not askyesno(self, _("Warning"),
                _("Directory exists:\n%s\nContinute?") % directory
            ):
                return
        else:
            try:
                makedirs(directory, exist_ok = True)
            except:
                ErrorDialog(
                    summary = _("Cannot create worktree %s") % directory,
                    message = format_exc()
                )
                return

        options = dict()

        version = self.git_ver_sel_widget.selected.get()
        if version:
            options["version"] = version

        new_branch = self.var_new_branch.get()
        if new_branch:
            options["new_branch"] = new_branch

        # Keep order in sync with __init__.
        self._result = self.qrepo, directory, options
        self.destroy()


class BuildDirCreationDialog(GUIDialog):

    def __init__(self, master,
        # Keep those args with sync with result (see _on_create_build_dir)
        qworktree,
        directory = "",
        **kw
    ):
        GUIDialog.__init__(self, master, **kw)
        self.qwt = qworktree

        self.title(_("Build directory creation"))

        self.columnconfigure(0, weight = 0)
        self.columnconfigure(1, weight = 1)
        self.columnconfigure(2, weight = 0)

        row = 0
        # Main: path to work tree
        self.rowconfigure(row, weight = 0)
        VarLabel(self, text = _("Work tree:")).grid(
            row = row,
            column = 0,
            sticky = "E"
        )
        Label(self, text = qworktree.path).grid(
            row = row,
            column = 1,
            sticky = "W",
            columnspan = 2
        )

        # Build directory: path to new build directory, Browse
        row += 1; self.rowconfigure(row, weight = 0)
        VarLabel(self, text = _("Directory:")).grid(
            row = row,
            column = 0,
            sticky = "E"
        )
        self.var_build_dir = StringVar(value = directory)
        HKEntry(self, textvariable = self.var_build_dir, width = 100).grid(
            row = row, column = 1, sticky = "NESW"
        )
        VarButton(self, text = _("Browse"), command = self._on_browse_bd).grid(
            row = row, column = 2
        )

        # Buttons
        row += 1; self.rowconfigure(row, weight = 0)
        bt_frame = GUIFrame(self)
        bt_frame.grid(row = row, column = 0, columnspan = 3, sticky = "NES")

        VarButton(bt_frame,
            text = _("Create"),
            command = self._on_create_build_dir
        ).pack()

    def _on_browse_bd(self):
        cur = self.var_build_dir.get()
        self.var_build_dir.set(
            askdirectory(self,
                title = _("Select build directory"),
                # we want to suggest a directory near working tree
                initialdir = cur or dirname(self.qwt.path)
            )
            or cur
        )

    def _on_create_build_dir(self):
        self._result = self.qwt, self.var_build_dir.get(), {}
        self.destroy()


if __name__ == "__main__":
    exit(main() or 0)
