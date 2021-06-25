from common import (
    mlget as _,
    notifier,
    makedirs,
    listen_all,
    QRepo,
    BuildDir,
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
        "__dict__"
    )

    def __init__(self, name, base = None, **changes):
        self.name = name
        self.base = base
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


class LauncherGUI(GUITk):

    def __init__(self, measurer, *a, **kw):
        GUITk.__init__(self, *a, **kw)

        self.title(_("Qemu Launcher"))

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)

        self.t_status = t_status = GUIText(self, state = READONLY)
        t_status.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(self, t_status, sizegrip = True)

        self._measurer = measurer

        for e in measurer._events:
            getattr(measurer, "watch_" + e)(getattr(self, "_on_" + e))

    def _on_build_started(self, ml):
        self.t_status.insert(END, "Building...\n" + str(ml))

    def _on_launched(self, ml, ql, proc):
        self.t_status.insert(END, "\n\nRunning...\n" +  " \\\n".join(proc.args))

    def _on_finished(self, ml, ql, proc):
        self.t_status.insert(END, "\n\nFinished (%d)\n\n" % proc.returncode)


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
        cleanup = False,
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

    i386 = base_launch.variant(".i386",
        arch = "i386",
        build = join(builds, "i386", "build"),
        prefix = join(builds, "i386", "install"),
        updates = dict(
            extra_configure_args = {
                "target-list" : "i386-softmmu",
            }
        )
    )

    i386XP = i386.variant(".WinXP",
        cwd = join(workdir, "winxp"),
        resdir = join(resdir, "winxp"),
        updates = dict(
            qemu_extra_args = dict(
                m = "1G",
                hda = join(workloads, "WinXPSP3i386/WinXPSP3i386_agent.qcow"),
                snapshot = True,
            )
        )
    )

    measurer = Measurer(
        i386XP.variant(".count",
            updates = dict(
                qemu_extra_args = dict(
                    rr3 = "count",
                ),
            )
        ),
        i386XP.variant(".save",
            updates = dict(
                qemu_extra_args = dict(
                    rr3 = "save",
                ),
            )
        ),
        i386XP.variant(".play",
            updates = dict(
                qemu_extra_args = dict(
                    rr3 = "play",
                ),
            )
        ),
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
