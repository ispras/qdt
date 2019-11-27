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

try:
    QEMU = environ["MSP430_QEMU"]
except:
    print("""MSP430_QEMU environment variable should point to Qemu binaries. \
Ex. /home/user/qemu/bin/qemu-system-msp430.
Qemu MSP430 available on github: \
https://github.com/dimas3452/qemu/tree/target-msp430"""
    )


c2t_cfg = C2TConfig(
    rsp_target = DebugClient(
        march = "msp430f5x",
        new_rsp = get_new_rsp(
            regs = list("r%d" % i for i in range(16)),
            pc = "r0",
            regsize = 16
        ),
        test_timeout = 30.,
        sp = "r1"
    ),
    qemu = DebugServer(
        Run(
            executable = QEMU,
            args = "-M msp430f5x -S -gdb tcp:localhost:{port} -nographic "
                "-kernel {bin}"
        )
    ),
    gdbserver = DebugServer(Run(
            executable = "/usr/bin/gdbserver",
            args = "localhost:{port} {bin}"
    )),
    target_compiler = TestBuilder(
        Run(
            executable = join(TOOLCHAIN, "bin", "msp430-elf-gcc"),
            args = "-I{0} -L{0} -mmcu=msp430f5xx_6xxgeneric -g -O0"
                " -o {{bin}} {{src}}".format(join(SUPPORT, "include"))
        )
    ),
    oracle_compiler = TestBuilder(
        Run(
            executable = "/usr/bin/gcc",
            args = "-g -O0 {src} -o {bin} -no-pie"
        )
    )
)
