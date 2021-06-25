from common import (
    mlget as _,
    notifier,
    makedirs,
    listen_all,
    QRepo,
    BuildDir,
    bidict,
)
from qemu import (
    QLaunch,
    ExampleQemuProcess,
)
from widgets import (
    add_scrollbars_native,
    GUITk,
    GUIText,
    READONLY,
    GUIFrame,
    VarTreeview,
    AutoPanedWindow,
)
from time import (
    time,
)
from traceback import (
    format_exc,
)
from threading import (
    Thread,
)
from six.moves.tkinter import (
    END,
    BOTH,
    BROWSE,
)
from argparse import (
    ArgumentParser,
)
from os import (
    remove,
)
from os.path import (
    abspath,
    dirname,
    exists,
    join,
)
from shutil import (
    rmtree,
    copyfile,
)
from collections import (
    defaultdict,
)


EMPTY_DICT = {}

@notifier(
    "build_started", # MeasureLaunch
    "launched",
        # MeasureLaunch, QemuBootTimeMeasureLaunch, QemuBootTimeMeasurer
    "finished",
        # MeasureLaunch, QemuBootTimeMeasureLaunch, QemuBootTimeMeasurer
)
class MeasureLaunch(object):

    __slots__ = (
        "name",
        "base",
        "variants",
        "__dict__"
    )

    def __init__(self, name, base = None, **changes):
        self.name = name
        self.base = base
        self.variants = []
        if base is not None:
            base.variants.append(self)

        for a, v in changes.items():
            setattr(self, a, v)

    def iter_attrs(self):
        overwritten = set()
        overwrite = overwritten.add

        for a, v in self.__dict__.items():
            yield a, v
            overwrite(a)

        if self.base is not None:
            for a, v in self.base.iter_attrs():
                if a not in overwritten:
                    yield a, v

    def __str__(self):
        attrs = list(self.iter_attrs())
        attrs.sort()

        attrs.insert(0, ("name", self.name))

        return "MeasureLaunch:\n  " + "\n  ".join(
            "%s = %s" % av for av in attrs if not av[0].startswith('_')
        )

    def variant(self, name_suffix, updates = {}, **changes):
        ret = type(self)(self.name + name_suffix, base = self, **changes)

        for a, v in updates.items():
            new_v = getattr(ret, a, EMPTY_DICT).copy()
            new_v.update(v)
            setattr(ret, a, new_v)

        return ret

    # inherit `base`'s value
    def __getattr__(self, name):
        if self.base is None:
            raise AttributeError(name)
        return getattr(self.base, name)

    def co_launch(self):
        qrepo = self.qrepo

        try:
            worktree = qrepo.worktree
        except:
            yield qrepo.co_get_worktrees()
            worktree = qrepo.worktree

        build_dir = BuildDir(worktree,
            path = self.build,
            prefix = self.prefix,
            extra_configure_args = self.extra_configure_args,
        )

        self.__notify_build_started(self)

        yield build_dir.co_install()

        qemu = join(build_dir.prefix, "bin", "qemu-system-" + self.arch)

        cwd = self.cwd

        makedirs(cwd, exist_ok = True)

        yield True
        launch = QemuBootTimeMeasureLaunch(qemu,
            process_kw = dict(
                cwd = cwd,
            ),
            extra_args = self.qemu_extra_args,
        )

        p = launch.launch(self.task_manager)

        self.__notify_launched(self, launch, p)

        poll = p.poll

        while poll() is None:
            yield False

        if p.returncode == 0:
            resdir = self.resdir
            resprefix = self.resprefix

            for fn in self.resfiles:
                src = join(cwd, fn)
                if exists(src):
                    dst = join(resdir, resprefix + fn)

                    makedirs(dirname(dst), exist_ok = True)
                    yield True

                    copyfile(src, dst)

                yield True

        if self.cleanup:
            rmtree(cwd)
            yield True

        self.__notify_finished(self, launch, p)


@notifier(
    "build_started", # see MeasureLaunch
    "launched",
    "finished",
)
class Measurer(object):

    def __init__(self, *measurements):
        self.measurements = list(measurements)

    def co_main(self):
        notify_pfx = "_" + type(self).__name__ + "__notify_"

        for m in self.measurements:
            for e in self._events:
                getattr(m, "watch_" + e)(getattr(self, notify_pfx + e))

            yield m.co_launch()

            for e in self._events:
                getattr(m, "unwatch_" + e)(getattr(self, notify_pfx + e))


@notifier(
    "finished",
)
class QemuBootTimeMeasurer(ExampleQemuProcess):

    def qmp_ready(self):
        print("Resuming...")
        self.t_resumed = time()
        self.qmp("cont")

    def co_serial(self, idx, remote):
        sup_gen = super(QemuBootTimeMeasurer, self).co_serial(idx, remote)

        chunk = None

        while True:
            chunk = (yield sup_gen.send(chunk))
            text = chunk.decode("utf-8")
            if "QDTAgent1" in text:
                self.t_qdt_agent_started = time()
                self.qmp("quit")

    def finished(self):
        self.__notify_finished()
        try:
            boot_duration = self.t_qdt_agent_started - self.t_resumed
        except:
            print("Can't measure boot duration...\n" + format_exc())
        else:
            self.boot_duration = boot_duration
            print("Boot duration: " + str(boot_duration))


class QemuBootTimeMeasureLaunch(QLaunch):

    def __init__(self, binary, **kw):
        kw["paused"] = True
        kw["qmp"] = True
        kw["serials"] = max(1, kw.get("serials", 1))
        super(QemuBootTimeMeasureLaunch, self).__init__(binary, **kw)

    def launch(self, *a, **kw):
        kw["ProcessClass"] = QemuBootTimeMeasurer
        return super(QemuBootTimeMeasureLaunch, self).launch(*a, **kw)


class LauncherThread(Thread):

    def __init__(self, launches, launcher_gui, log = None, **kw):
        super(LauncherThread, self).__init__(**kw)
        self.launches = launches
        self.gui = launcher_gui
        self.log = log

        self._working = True
        self._current_proc = None

        launcher_gui.bind("<Destroy>", self._on_gui_destroy)

    def run(self):
        log = self.log

        if log is not None:
            log_file = open(log, "a+")
            write = log_file.write
            flush = log_file.flush

            def write_and_flush(*a, **kw):
                write(*a, **kw)
                flush()

            listener = listen_all(write_and_flush, locked = True)

        gui = self.gui
        tm = gui.task_manager
        for launch in self.launches:

            if not self._working:
                break

            p = launch.launch(tm)

            self._current_proc = p

            gui.sig_launched(launch, p)
            p.wait()
            gui.sig_finished(launch, p)

        if log is not None:
            listener.revert()
            log_file.close()

        gui.sig_launcher_ended()

    def _on_gui_destroy(self, __):
        self._working = False
        if self._current_proc is not None:
            self._current_proc.terminate()


class LaunchInfoWidget(GUIFrame):

    def __init__(self, master, *a, **kw):
        sizegrip = kw.pop("sizegrip", False)
        GUIFrame.__init__(self, master, *a, **kw)

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)

        self.t_status = t_info = GUIText(self, state = READONLY)
        t_info.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(self, t_info, sizegrip = sizegrip)

    def set_info(self, info):
        self.t_status.delete("1.0", END)
        self.t_status.insert(END, info)


class LaunchTree(GUIFrame):

    def __init__(self, master, *a, **kw):
        sizegrip = kw.pop("sizegrip", False)
        GUIFrame.__init__(self, master, *a, **kw)

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)

        self.tv = tv = VarTreeview(self,
            selectmode = BROWSE,
            columns = ["status"],
        )

        tv.grid(row = 0, column = 0, sticky = "NESW")
        add_scrollbars_native(self, tv, sizegrip = sizegrip)

        tv.heading("#0", text = _("Launch"))
        tv.column("#0", width = 350)

        tv.heading("status", text = _("Status"))
        tv.column("status", width = 80)

        self.iid2launch = bidict()

        tv.bind("<<TreeviewSelect>>", self._on_tv_select, "+")
        self.selected = None

    def set_status(self, launch, status):
        self.tv.item(self.iid2launch.mirror[launch],
            values = [status],
        )

    def set_launches(self, launches):
        self.tv.delete(*self.tv.get_children())

        for launch in launches:
            self._insert_row_for_launch(launch)

    def _insert_row_for_launch(self, launch):
        iid2launch = self.iid2launch
        base = launch.base

        if base is None:
            parent = ""
        else:
            try:
                parent = iid2launch.mirror[base]
            except KeyError:
                parent = self._insert_row_for_launch(base)

        iid = self.tv.insert(parent, END,
            open = True,
            text = launch.name,
        )
        iid2launch[iid] = launch

        return iid

    def _on_tv_select(self, *__):
        sels = self.tv.selection()
        if sels:
            self.selected = self.iid2launch[sels[0]]
        else:
            self.selected = None

        self.event_generate("<<LaunchSelect>>")


class LauncherGUI(GUITk):

    def __init__(self, measurer, *a, **kw):
        GUITk.__init__(self, *a, **kw)

        self.title(_("Qemu Launcher"))

        self._measurer = measurer

        apw = AutoPanedWindow(self)
        apw.pack(fill = BOTH, expand = True)

        self.w_tree = w_tree = LaunchTree(apw)
        apw.add(w_tree, sticky = "NESW")

        self.w_info = w_status = LaunchInfoWidget(apw, sizegrip = True)
        apw.add(w_status, sticky = "NESW")

        w_tree.set_launches(measurer.measurements)

        self.info = defaultdict(str)

        for e in measurer._events:
            getattr(measurer, "watch_" + e)(getattr(self, "_on_" + e))

        w_tree.bind("<<LaunchSelect>>", self._on_launch_select, "+")

    def _on_build_started(self, ml):
        self.info[ml] += "Building...\n"
        self.w_tree.set_status(ml, "building")
        self._update_info(ml)

    def _on_launched(self, ml, ql, proc):
        self.info[ml] += "\n\nRunning...\n" +  " \\\n".join(proc.args)
        self.w_tree.set_status(ml, "running")
        self._update_info(ml)

    def _on_finished(self, ml, ql, proc):
        rc = proc.returncode

        self.info[ml] += "\n\nFinished (%d)\n\n" % rc

        if rc == 0:
            self.w_tree.set_status(ml, "finished")
        else:
            self.w_tree.set_status(ml, "failed (%d)" % rc)

        self._update_info(ml)

    def _update_info(self, launch):
        if launch is self.w_tree.selected:
            info = str(launch) + "\n\n" + self.info[launch]

            self.w_info.set_info(info)

    def _on_launch_select(self, e):
        launch = e.widget.selected
        if launch is None:
            info = ""
        else:
            info = str(launch) + "\n\n" + self.info[launch]

        self.w_info.set_info(info)


def main():
    ap = ArgumentParser()
    ap.add_argument("qemu",
        help = "qemu worktree (sources)",
    )
    ap.add_argument("--builds",
        default = join(".", "builds"),
        help = "where to build qemu",
    )
    ap.add_argument("--workdir",
        default = join(".", "work"),
        help = "where to launch qemu",
    )
    ap.add_argument("--resdir",
        default = join(".", "res"),
        help = "where to copy results",
    )
    ap.add_argument("--workloads",
        default = ".",
        help = "guest images"
    )
    ap.add_argument("--log", default = None)
    ap.add_argument("--new-log", action = "store_true")

    args = ap.parse_args()

    qemu = abspath(args.qemu)
    builds = abspath(args.builds)
    workdir = abspath(args.workdir)
    resdir = abspath(args.resdir)
    workloads = abspath(args.workloads)

    log = args.log

    qrepo = QRepo(qemu)

    base_launch = MeasureLaunch("Qemu",
        qrepo = qrepo,
        cleanup = True,
        resfiles = (
            "count.csv",
            "save.csv",
            "play.csv",
            "shadows.save.txt",
            "shadows.play.txt",
            "statistics.txt",
        ),
        resprefix = "",
        extra_configure_args = dict(
            vte = True,
            sdl = False,
            rr3 = True,
        )
    )

    def gen_arches(base, arches, **__):
        for arch in arches:
            yield base.variant("." + arch,
                arch = arch,
                build = join(builds, arch, "build"),
                prefix = join(builds, arch, "install"),
                updates = dict(
                    extra_configure_args = {
                        "target-list" : arch + "-softmmu",
                    }
                )
            )

    def gen_workloads(base, **__):
        yield base.variant(".WinXP",
            cwd = join(workdir, "winxp"),
            resdir = join(resdir, "winxp"),
            updates = dict(
                qemu_extra_args = dict(
                    m = "1G",
                    hda = join(
                        workloads, "WinXPSP3i386/WinXPSP3i386_agent.qcow"
                    ),
                    snapshot = True,
                )
            )
        )

    def gen_rr3_variants(base, **__):
        yield base.variant(".count",
            updates = dict(
                qemu_extra_args = dict(
                    rr3 = "count",
                ),
            )
        )
        yield base.variant(".save",
            cleanup = False,
            updates = dict(
                qemu_extra_args = dict(
                    rr3 = "save",
                ),
            )
        )
        yield base.variant(".play",
            updates = dict(
                qemu_extra_args = dict(
                    rr3 = "play",
                ),
            )
        )

    def gen_multiple(base, times, **__):
        for i in range(times):
            yield base.variant("." + str(i),
                resprefix = str(i) + "." + base.resprefix,
            )

    def gen_tree(base, gen0, *rest_gen, **conf):
        if rest_gen:
            for variant in gen0(base, **conf):
                for res in gen_tree(variant, *rest_gen, **conf):
                    yield res
        else:
            for res in gen0(base, **conf):
                yield res


    measurer = Measurer(
        *gen_tree(base_launch,
            gen_arches,
            gen_workloads,
            gen_multiple,
            gen_rr3_variants,
            times = 3,
            arches = ("i386", "x86_64")
        )
    )

    root = LauncherGUI(measurer)

    base_launch.task_manager = root.task_manager

    if log is not None:
        log = abspath(log)
        makedirs(dirname(log), exist_ok = True)

        if args.new_log:
            if exists(log):
                remove(log)

        log_file = open(log, "a+")
        write = log_file.write
        flush = log_file.flush

        def write_and_flush(*a, **kw):
            write(*a, **kw)
            flush()

        listener = listen_all(write_and_flush, locked = True)

    root.task_manager.enqueue(measurer.co_main())

    root.mainloop()

    if log is not None:
        listener.revert()
        log_file.close()


if __name__ == "__main__":
    exit(main() or 0)
