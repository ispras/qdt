from common import (
    mlget as _,
)
from qemu import (
    QLaunch,
    ExampleQemuProcess,
)
from widgets import (
    GUITk,
)
from collections import (
    OrderedDict,
)


def main():
    root = GUITk()
    root.title(_("Qemu Launcher"))

    l = QLaunch(
        "/home/real/work/qemu/retrace3/noretrace_5.2.0/opt/install/bin/qemu-system-i386",
        paused = False,
        qmp = True,
        serials = 1,
        extra_args = OrderedDict(
            accel = "kvm",
            m = "1G",
            hda = "/media/data/Docs/ISPRAS/qemu/workloads/WinXPSP3i386/WinXPSP3i386_agent.qcow",
            snapshot = True,
            shutdown = False,
            usb = True,
            device = [
                "usb-ehci,id=ehci",
                "usb-host,vendorid=0x0b95,productid=0x7720",
            ],
            netdev = "user,id=n1,smb=/home/real/work/qemu/device_creator/agent",
            net = "nic,model=rtl8139,netdev=n1",
        )
    )

    qproc = l.launch(root.task_manager, ProcessClass = ExampleQemuProcess)

    root.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
