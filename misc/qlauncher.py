from common import (
    mlget as _,
    notifier,
    makedirs,
    listen_all,
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
from itertools import (
    count,
)


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

    def __init__(self, *a, **kw):
        GUITk.__init__(self, *a, **kw)

        self.title(_("Qemu Launcher"))

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)

        self.t_status = t_status = GUIText(self, state = READONLY)
        t_status.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(self, t_status, sizegrip = True)

        sd = self.signal_dispatcher
        self.sig_launched = sd.new_signal(self._on_launched)
        self.sig_finished = sd.new_signal(self._on_finished)
        self.sig_launcher_ended = sd.new_signal(self._on_launcher_ended)

    def _on_launched(self, launch, proc):
        self.t_status.insert(END, " \\\n".join(proc.args))

    def _on_finished(self, launch, proc):
        self.t_status.delete("1.0", END)

    def _on_launcher_ended(self):
        self.destroy()


def main():
    ap = ArgumentParser()
    ap.add_argument("--qemu", default = "qemu-system-i386")
    ap.add_argument("--smbroot", default = abspath("."))
    ap.add_argument("--workloads", default = abspath("."))
    ap.add_argument("--records", default = abspath("."))
    ap.add_argument("--log", default = None)
    ap.add_argument("--new-log", action = "store_true")

    args = ap.parse_args()

    qemu = args.qemu
    smbroot = args.smbroot
    workloads = args.workloads
    records = args.records

    makedirs(smbroot, exist_ok = True)

    def record_dir_gen():
        for i in count():
            dirname = join(records, str(i))
            if exists(dirname):
                continue
            makedirs(dirname)
            yield dirname

    rec_dir_iter = iter(record_dir_gen())

    log = args.log

    if log is not None:
        log = abspath(log)
        makedirs(dirname(log), exist_ok = True)

        if args.new_log:
            if exists(log):
                remove(log)

    root = LauncherGUI()

    rec_winxp = next(rec_dir_iter)

    launches = [
        QemuBootTimeMeasureLaunch(qemu,
            process_kw = dict(
                cwd = rec_winxp
            ),
            extra_args = dict(
                m = "1G",
                hda = join(workloads, "WinXPSP3i386/WinXPSP3i386_agent.qcow"),
                snapshot = True,
                rr3 = "count",
            )
        ),
        QemuBootTimeMeasureLaunch(qemu,
            process_kw = dict(
                cwd = rec_winxp
            ),
            extra_args = dict(
                m = "1G",
                hda = join(workloads, "WinXPSP3i386/WinXPSP3i386_agent.qcow"),
                snapshot = True,
                rr3 = "save",
            )
        ),
        QemuBootTimeMeasureLaunch(qemu,
            process_kw = dict(
                cwd = rec_winxp
            ),
            extra_args = dict(
                m = "1G",
                hda = join(workloads, "WinXPSP3i386/WinXPSP3i386_agent.qcow"),
                snapshot = True,
                rr3 = "play",
            )
        ),
        QemuBootTimeMeasureLaunch(qemu,
            extra_args = dict(
                m = "1G",
                hda = join(workloads, "WinXPSP3i386/WinXPSP3i386_agent.qcow"),
                snapshot = True,
            )
        ),
        QemuBootTimeMeasureLaunch(qemu,
            extra_args = dict(
                accel = "kvm",
                m = "1G",
                hda = join(workloads, "WinXPSP3i386/WinXPSP3i386_agent.qcow"),
                snapshot = True,
                # shutdown = False,
                usb = True,
                device = [
                    "usb-ehci,id=ehci",
                    "usb-host,vendorid=0x0b95,productid=0x7720",
                ],
                netdev = "user,id=n1,smb=" + smbroot,
                net = "nic,model=rtl8139,netdev=n1",
            )
        ),
    ]

    LauncherThread(launches, root, log = log).start()

    root.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
