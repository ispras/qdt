from common import (
    mlget as _,
    notifier,
)
from qemu import (
    QLaunch,
    ExampleQemuProcess,
)
from widgets import (
    GUITk,
)
from time import (
    time,
)
from traceback import (
    format_exc,
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


def main():
    root = GUITk()
    root.title(_("Qemu Launcher"))

    launches = [
        QemuBootTimeMeasureLaunch(
            "/home/real/work/qemu/retrace3/noretrace_5.2.0/opt/install/bin/qemu-system-i386",
            extra_args = dict(
                accel = "kvm",
                m = "1G",
                hda = "/media/data/Docs/ISPRAS/qemu/workloads/WinXPSP3i386/WinXPSP3i386_agent.qcow",
                snapshot = True,
                # shutdown = False,
                usb = True,
                device = [
                    "usb-ehci,id=ehci",
                    "usb-host,vendorid=0x0b95,productid=0x7720",
                ],
                netdev = "user,id=n1,smb=/home/real/work/qemu/device_creator/agent",
                net = "nic,model=rtl8139,netdev=n1",
            )
        ),
        QemuBootTimeMeasureLaunch(
            "/home/real/work/qemu/retrace3/opt/install/bin/qemu-system-i386",
            extra_args = dict(
                m = "1G",
                hda = "/media/data/Docs/ISPRAS/qemu/workloads/WinXPSP3i386/WinXPSP3i386_agent.qcow",
                snapshot = True,
            )
        ),
    ]

    qproc = launches[1].launch(root.task_manager)

    qproc.watch_finished(lambda : root.after(1, root.destroy))

    root.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
