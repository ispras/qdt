from os import (
    environ
)
from os.path import (
    join
)

try:
    TOOLCHAIN = environ["MSP430_TOOLCHAIN"]
except:
    print("""MSP430_TOOLCHAIN environment variable should point to folder \
with compiler toolchain. Ex. /home/user/msp430-gcc-7.3.2.154_linux64.
Toolchain available at: \
http://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/MSPGCC/6_1_1_0/\
index_FDS.html"""
    )
    raise

try:
    SUPPORT = environ["MSP430_SUPPORT"]
except:
    print("""MSP430_SUPPORT environment variable should point to folder with \
headers. Ex. /home/user/msp430-gcc-support-files.
Support files available at: \
http://software-dl.ti.com/msp430/msp430_public_sw/mcu/msp430/MSPGCC/6_1_1_0/\
exports/msp430-gcc-support-files-1.207.zip"""
    )
    raise

try:
    QEMU = environ["MSP430_QEMU"]
except:
    print("""MSP430_QEMU environment variable should point to Qemu binaries. \
Ex. /home/user/qemu/bin/qemu-system-msp430.
Qemu MSP430 available on github: \
https://github.com/dimas3452/qemu/tree/target-msp430"""
    )
    raise

QLOG = bool(eval(environ.get("MSP430_QEMU_LOG", "False")))

"""
Test selection args:

-t ^.+\\.c$

-s ^_readme_.*$
Because some breakpoints have multiple adresses and that confuses c2t.

-s ^.*m_stack_u?((32)|(64)).*$
Because machine have only 512 bytes of RAM.
There is 50 variables & 50 function
arguments. Each 4 bytes (8 bytes in 64 tests). Total 400 bytes (theoretically).
Compiller generates the code of `main` that using 23Ch bytes of stack, it's
572 bytes...

"""

qemu_args = "-M msp430_test -S -gdb tcp:localhost:{port} -nographic"
if QLOG:
    qemu_args += " -singlestep -d in_asm,cpu,exec -D {bin}.qlog"

c2t_cfg = C2TConfig(
    rsp_target = DebugClient(
        march = "msp430g2553",
        new_rsp = get_new_rsp(
            regs = list("r%d" % i for i in range(16)),
            pc = "r0",
            regsize = 16
        ),
        # Some tests run long enough.
        test_timeout = 40.,
        sp = "r1"
    ),
    qemu = DebugServer(
        Run(
            executable = QEMU,
            args = qemu_args
        )
    ),
    gdbserver = DebugServer(Run(
            executable = "/usr/bin/gdbserver",
            args = "localhost:{port} {bin}"
    )),
    target_compiler = TestBuilder(
        Run(
            executable = join(TOOLCHAIN, "bin", "msp430-elf-gcc"),
            args = "-I{0} -L{0} -mmcu=msp430g2553 -g -O0"
                " -o {{bin}} {{src}}".format(join(SUPPORT, "include"))
        ),
        Run(
            executable = join(TOOLCHAIN, "bin", "msp430-elf-objdump"),
            args = "-D {bin} > {ir}.disas"
        )
    ),
    oracle_compiler = TestBuilder(
        Run(
            executable = "/usr/bin/gcc",
            args = "-g -O0 {src} -o {bin} -no-pie"
        )
    )
)
