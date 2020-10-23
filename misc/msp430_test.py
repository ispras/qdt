#!/usr/bin/python

from os.path import (
    isdir,
    join,
    isfile,
    exists,
)
from os import (
    listdir
)
from common import (
    pypath,
    ee,
    ThreadStreamCopier,
    PortPool,
)
from subprocess import (
    Popen,
    PIPE
)
from c2t import (
    get_new_rsp,
)
from debug import (
    RSPWatcher,
)
from threading import (
    Thread,
    Lock,
    Condition,
)
from argparse import (
    ArgumentParser,
)
# use ours pyrsp
with pypath("..pyrsp"):
    from pyrsp.utils import (
        wait_for_tcp_port
    )


ENERGIA_PATH = ee("ENERGIA_PATH", "None")
MSP430_TOOLCHAIN = ee("MSP430_TOOLCHAIN", "None")
MSP430_SUPPORT = ee("MSP430_SUPPORT", "None")
QEMU_MSP430 = ee("QEMU_MSP430", "None")
QEMU_MSP430_ARGS = ee("QEMU_MSP430_ARGS",
    '["-M", "msp430x2xx", "-nographic"]'
)

TESTS_PATH = ee("MSP430_TESTS_PATH")


def set_paths():
    global TOOLCHAIN_BIN
    global MSPDEBUG
    global MSP430_PFX
    global EXTRA_CFLAGS

    if ENERGIA_PATH is None:
        if (MSP430_TOOLCHAIN and MSP430_SUPPORT) is None:
            print("Set either ENERGIA_PATH or MSP430_TOOLCHAIN/MSP430_SUPPORT"
                " env. varisables"
            )
            exit(3)
        if not isdir(MSP430_TOOLCHAIN) or not isdir(MSP430_SUPPORT):
            print("Set both MSP430_TOOLCHAIN and MSP430_SUPPORT or set "
                "ENERGIA_PATH env.var."
            )
            exit(4)

        TOOLCHAIN_BIN = join(MSP430_TOOLCHAIN, "bin")
        # sudo apt install mspdebug
        MSPDEBUG = "mspdebug"
        MSP430_PFX = "msp430-elf-"
        EXTRA_CFLAGS = [
            "-L" + join(MSP430_SUPPORT, "include"),
        ]
    else:
        if not isdir(ENERGIA_PATH):
            print("Check ENERGIA_PATH env. var.")
            exit(1)

        TOOLCHAIN_BIN = join(
            ENERGIA_PATH, "hardware", "tools", "msp430", "bin"
        )
        MSPDEBUG = join(
            ENERGIA_PATH, "hardware", "tools", "mspdebug", "mspdebug",
        )
        MSP430_PFX = "msp430-"
        EXTRA_CFLAGS = []

    if not isdir(TESTS_PATH):
        print("Check MSP430_TESTS_PATH env. var.")
        exit(2)

    if QEMU_MSP430 is None or not isfile(QEMU_MSP430):
        print("Set path to qemu executable through QEMU_MSP430 env. var.")
        exit(5)

set_paths()

GCC = join(TOOLCHAIN_BIN, MSP430_PFX + "gcc")
AS = join(TOOLCHAIN_BIN, MSP430_PFX + "as")
READELF = join(TOOLCHAIN_BIN, MSP430_PFX + "readelf")
OBJCOPY = join(TOOLCHAIN_BIN, MSP430_PFX + "objcopy")
OBJDUMP = join(TOOLCHAIN_BIN, MSP430_PFX + "objdump")
GDB = join(TOOLCHAIN_BIN, MSP430_PFX + "gdb")


def msp430_as(name, mcu = "msp430g2553"):
    # msp430-as -c -mmcu=msp430g2553 -o test.o test.s
    p = Popen([AS, "-c", "-mmcu=" + mcu,
            "-g",
            "-o", name + ".o", name + ".s"
        ],
        stdin = PIPE,
        cwd = TESTS_PATH,
    )
    return p.wait()


def msp430_link(name, mcu = "msp430g2553"):
    # msp430-gcc -fno-rtti -fno-exceptions -Wl,--gc-sections,-u,main
    #    -mmcu=msp430g2553 -L{SUPPORT_INCLUDE} -o test.elf test.o
    p = Popen([GCC] + EXTRA_CFLAGS + [
            "-g",
            "-mmcu=" + mcu, "-o", name + ".elf",
            name + ".o", "main.o"
        ],
        stdin = PIPE,
        cwd = TESTS_PATH,
    )
    return p.wait()


def msp430_disas(name):
    with open(join(TESTS_PATH, name + ".disas"), "wb") as f:
        p = Popen([OBJDUMP, "-d", name + ".elf"],
            stdout = f,
            stdin = PIPE,
            cwd = TESTS_PATH,
        )
        return p.wait()


def msp430_readelf(name):
    with open(join(TESTS_PATH, name + ".elf.txt"), "wb") as f:
        p = Popen([READELF, "-a", name + ".elf"],
            stdout = f,
            stdin = PIPE,
            cwd = TESTS_PATH,
        )
        return p.wait()


def msp430_objcopy(name):
    # msp430-objcopy -O ihex -R .eeprom test.elf test.hex
    p = Popen([OBJCOPY, "-O", "ihex", "-R", ".eeprom", name + ".elf",
            name + ".hex"
        ],
        stdin = PIPE,
        cwd = TESTS_PATH,
    )
    return p.wait()


def msp430_load(name):
    # mspdebug rf2500 --force-reset prog test.hex
    p = Popen([MSPDEBUG, "rf2500", "--force-reset", "prog %s.hex" % name],
        stdin = PIPE,
        cwd = TESTS_PATH,
    )
    return p.wait()


def msp430_start_debug():
    # mspdebug rf2500 gdb
    return Popen([MSPDEBUG, "rf2500", "gdb"],
        stdin = PIPE,
        cwd = TESTS_PATH,
    )


def msp430_gdb_py(name):
    pass


MSP430_REGS = tuple(("r%d" % i) for i in range(16))

MSP430RSP = get_new_rsp(MSP430_REGS, "r0", 16)


class MSPDebugRSP(MSP430RSP):

    @property
    def thread(self):
        return self._thread

    @thread.setter
    def thread(self, pid_tid):
        self._thread = pid_tid
        # mspdebug's RSP does not support Hg command


# We only have one board and should share it among threads carefully
BOARD_LOCK = Lock()


copier = ThreadStreamCopier.catch_stdout()

port_pool = PortPool()


def main():
    ap = ArgumentParser("MSP430 Hardware Based Test Utility")
    ap.add_argument("tests",
        nargs = "*",
        help = "select specific tests in MSP430_TESTS_PATH directory"
            " (without .s suffix)"
    )

    set_paths()

    args = ap.parse_args()

    jobs = 8

    QEMU_MSP430_ARGS.append("-S")

    if args.tests:
        tests = list(args.tests)
        for t in tests:
            t_full = join(TESTS_PATH, t + ".s")
            if not exists(t_full):
                raise ValueError("No such test file: " + t_full)
    else:
        tests = []
        for n in listdir(TESTS_PATH):
            if n.endswith(".s"):
                tests.append(n[:-2])

    if not tests:
        print("No tests found")
        return 0 # it's not an error

    mcu = "msp430g2553"

    p = Popen([GCC] + EXTRA_CFLAGS + [
            "-c",
            "-g",
            "-mmcu=" + mcu, "-o", "main.o", "main.c"
        ],
        stdin = PIPE,
        cwd = TESTS_PATH,
    )
    if p.wait():
        print("Can't build main wrapper")
        return 3

    print("tests: " + ", ".join(tests))

    hw_test_ready = Condition()
    hw_tests_queue = []

    qemu_test_ready = Condition()
    qemu_tests_queue = []

    for n in range(jobs // 2):
        Thread(
            name = "test_job_hw#" + str(n),
            target = test_job,
            args = (hw_tests_queue, hw_test_ready, hardware_handler, "hw")
        ).start()

        Thread(
            name = "test_job_qemu#" + str(n),
            target = test_job,
            args = (qemu_tests_queue, qemu_test_ready, qemu_handler, "qemu")
        ).start()


    for t in tests:
        print("Preparing test: " + t)

        # create object file
        if msp430_as(t):
            continue

        # create ELF file
        if msp430_link(t):
            continue

        msp430_disas(t)
        msp430_readelf(t)

        # create HEX file
        if msp430_objcopy(t):
            continue

        print("Preparation succeeded: " + t)

        with hw_test_ready:
            hw_tests_queue.append(t)
            hw_test_ready.notify(1)

        with qemu_test_ready:
            qemu_tests_queue.append(t)
            qemu_test_ready.notify(1)

    with hw_test_ready:
        hw_tests_queue.append(None) # None means no more tests
        hw_test_ready.notify_all()

    with qemu_test_ready:
        qemu_tests_queue.append(None)
        qemu_test_ready.notify_all()


def test_job(queue, cond, handler, backed_name):
    while True:
        while True:
            with cond:
                if queue:
                    if queue[0] is None:
                        print("No more tests")
                        return
                    t = queue.pop(0)
                    break

                cond.wait()

        log_file_name = join(TESTS_PATH, t + "." + backed_name + ".log")
        with open(log_file_name, "w") as log_file:
            with copier(log_file):
                do_test_job(t, handler)


def do_test_job(t, handler):
    ns = {}
    with pypath(TESTS_PATH):
        with pypath("..pyrsp"):
            exec("from %s import *" % t, ns)

    watchers = []

    for n, cls in ns.items():
        if not isinstance(cls, type):
            continue
        if cls is RSPWatcher:
            continue
        if issubclass(cls, RSPWatcher):
            print("Using " + n)
            watchers.append(cls)

    if not watchers:
        raise NotImplementedError("No RSPWatcher subclass class defined")

    def test_func(rsp, elf_file_name):
        for w in watchers:
            w(rsp, elf_file_name)

        rsp.run(setpc = False)

    handler(t, test_func)


def hardware_handler(t, test_func):
    with BOARD_LOCK:
        print("###\nTest: " + t + "\n###\n")

        # load HEX file
        if msp430_load(t):
            return

        # start debug server
        p = msp430_start_debug()

        try:
            wait_for_tcp_port(2000)

            rsp = MSPDebugRSP("2000")

            test_func(rsp, join(TESTS_PATH, t + ".elf"))
        finally:
            p.terminate()
            p.wait()


def qemu_handler(t, test_func):
    print("###\nTest: " + t + "\n###\n")

    elf_file_name = join(TESTS_PATH, t + ".elf")

    with port_pool() as port:
        p = Popen([QEMU_MSP430] + QEMU_MSP430_ARGS + [
                "-gdb", "tcp:localhost:" + str(port),
                "-S",
                "-kernel", elf_file_name
            ],
            stdin = PIPE,
            cwd = TESTS_PATH,
        )

        try:
            wait_for_tcp_port(port)

            rsp = MSPDebugRSP(str(port))

            test_func(rsp, elf_file_name)
        finally:
            p.terminate()
            p.wait()


if __name__ == "__main__":
    exit(main() or 0)
