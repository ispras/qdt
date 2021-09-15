""" Record/Replay Tester
"""

# our modules
from common import (
    CLICoDispatcher,
    BuildDir,
    pypath,
    QRepo,
)
with pypath("pyrsp"): # use ours pyrsp & pyelftools
    with pypath("debug/pyelftools"):
        from pyrsp.rsp import (
            i386,
        )
from debug import (
    create_dwarf_cache,
    Runtime,
    Watcher,
)
from qemu import (
    QLaunch,
    QemuProcess,
)

# outer modules
from argparse import (
    ArgumentParser,
)
from os.path import (
    abspath,
    dirname,
    join,
)
from traceback import (
    format_exc,
)


def main():
    script_dir = dirname(abspath(__file__))

    ap = ArgumentParser(
        description = "Record/Replay Tester",
    )
    arg = ap.add_argument

    arg("qemu",
        help = "Path to Qemu executable",
    )
    arg("--tests",
        nargs = "*",
        default = [
            join(script_dir, "llv"),
        ]
    )

    args = ap.parse_args()

    return rrt(**vars(args))


def rrt(qemu, tests):
    rrtests = list(
        RRTest(t,
            WatcherClass = CRCWatcher, # XXX: must not be hardcoded
        ) for t in tests
    )

    disp = CLICoDispatcher()
    disp.enqueue(co_run(rrtests, qemu, disp))
    disp.dispatch_all()


def co_run(rrtests, qemu, disp):
    for t in rrtests:
        yield t.co_run(qemu, disp)


class SimpleBuildDir(BuildDir):

    def need_configuration(self):
        return False

"""
-drive file=/media/data/Docs/ISPRAS/qemu/workloads/WinXPSP3i386/WinXPSP3i386_agent.qcow,if=none,id=img-direct,snapshot
-drive driver=blkreplay,if=none,image=img-direct,id=img-blkreplay
-device ide-hd,drive=img-blkreplay
-icount 2,rr=record,rrfile=/home/real/work/qemu/retrace3/records/3/icount.rr.bin
"""


class RRTest(object):

    def __init__(self, path, WatcherClass,
        # TODO: if True, launch witout record/replay twice.
        #       If test output differs, test is good.
        check_tests = False
    ):
        self.path = path
        self.WatcherClass = WatcherClass
        self.check_tests = check_tests

    def co_run(self, qemu, disp):
        path = self.path

        self.qrepo = qrepo = QRepo(self.path)

        yield qrepo.co_get_worktrees()

        self.build_dir = build_dir = SimpleBuildDir(None,
            # XXX: it sould not be hardcoded
            path = join(path, "02_01_int_chksum"),
            prefix = path,
            extra_build_args = (
                "ASFLAGS=-g", # for debug info
            )
        )

        yield build_dir.co_build()

        image_path = join(build_dir.path, "main.bin")

        # XXX: may be .32.elf
        elf_path = join(build_dir.path, "main.16.elf")

        rec_launch = QLaunch(qemu,
            paused = True,
            qmp = True,
            gdb = True,
            process_kw = dict(
                cwd = build_dir.path,
            ),
            extra_args = dict(
                drive = [
                    "file=%s,if=none,id=img-base,snapshot" % image_path,
                    "driver=blkreplay,if=none,image=img-base,id=img-blkr",
                ],
                device = [
                    "ide-hd,drive=img-blkr",
                ],
                icount = "2,rr=record,rrfile=rr.bin",
            ),
        )

        p = rec_launch.launch(disp,
            ProcessClass = RRTestProcess,
            elf_path = elf_path,
            WatcherClass = self.WatcherClass,
            disp_ = disp, # XXX: it's horrible
            mode = MODE_RECORD,
        )
        poll = p.poll

        while poll() is None:
            yield False

        p.wait_threads()

        if p.returncode:
            raise Exception("record failed")

        replay_launch = QLaunch(qemu,
            paused = True,
            qmp = True,
            gdb = True,
            process_kw = dict(
                cwd = build_dir.path,
            ),
            extra_args = dict(
                drive = [
                    "file=%s,if=none,id=img-base,snapshot" % image_path,
                    "driver=blkreplay,if=none,image=img-base,id=img-blkr",
                ],
                device = [
                    "ide-hd,drive=img-blkr",
                ],
                icount = "2,rr=replay,rrfile=rr.bin",
            ),
        )

        p = replay_launch.launch(disp,
            ProcessClass = RRTestProcess,
            elf_path = elf_path,
            WatcherClass = self.WatcherClass,
            disp_ = disp,
            mode = MODE_REPLAY,
        )
        poll = p.poll

        while poll() is None:
            yield False

        p.wait_threads()


class MODE_NORMAL: pass
class MODE_RECORD: pass
class MODE_REPLAY: pass


class RRTestProcess(QemuProcess):

    def __init__(self, args, elf_path, WatcherClass, disp_,
        mode = MODE_NORMAL,
        **kw
    ):
        print("Starting process: " + str(args))
        super(RRTestProcess, self).__init__(args, **kw)
        self.elf_path = elf_path
        self.WatcherClass = WatcherClass
        self.disp = disp_
        self.mode = mode

    def co_qmp(self, remote, version, capabilities):
        print("QMP: remote: %s: version: %s, capabilities: %s" % (
            remote,
            version,
            ", ".join(capabilities)
        ))

        while True:
            event = (yield)

            print("QMP: " + str(event))


    def qmp_ready(self):
        print("Initializing GDB Session...")

        try:
            dic = create_dwarf_cache(self.elf_path)

            # Else, dic can't find some breakpoints
            for cu in dic.iter_CUs():
                dic.account_line_program_CU(cu)

            self.watcher = watcher = self.WatcherClass(self, dic,
                verbose = True, # XXX: must be optional
            )

            debugger = i386(str(self.gdb_chardev.port),
                noack = True,
                verbose = True, # XXX: must be optional (different option)
            )

            self.rt = rt = Runtime(debugger, dic)
            watcher.init_runtime(rt)

            print("Resuming...")
            self.disp.enqueue(rt.co_run_target())
        except:
            print(format_exc())
            self.qmp("quit")

    def co_serial(self, idx, remote):
        prefix = "serial%d: " % idx
        print(prefix + "connection from " + str(remote))

        while True:
            chunk = (yield)
            text = chunk.decode("utf-8")

            print(prefix + text.rstrip("\r\n"))

    def co_operate(self):
        while True:
            stdout, stderr = (yield)

            if stdout:
                print("out: " + stdout.decode("utf-8").rstrip("\r\n"))
            if stderr:
                print("err: " + stderr.decode("utf-8").rstrip("\r\n"))

    def finished(self):
        print("Finished")


class RRWatcher(Watcher):

    def __init__(self, rr_test_process, *a, **kw):
        super(RRWatcher, self).__init__(*a, **kw)
        self.rr_test_process = rr_test_process


class CRCWatcher(RRWatcher):

    def on_infloop(self):
        """
main.asm:149 97004f69da7ba0072e480da5d1ac24e8ad69f760
        """

        rt = self.rt
        symbol = rt.dic.symtab.get_symbol_by_name("int_crc")[0]
        int_crc_addr = symbol.entry.st_value
        crc = rt.get_val(int_crc_addr, 2)

        print(
            "CRC: " + hex(crc)
          + " Mode: " + self.rr_test_process.mode.__name__
        )

        if self.rr_test_process.mode is MODE_RECORD:
            # Else, rr will not replay last instruction and this breakpoint
            # (as a result) too.
            rt.target.step()

        self.rr_test_process.qmp("quit")

        # TODO: compare crc(MODE_RECORD) vs crc(MODE_REPLAY)


if __name__ == "__main__":
    exit(main() or 0)
