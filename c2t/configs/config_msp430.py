from os import (
    environ
)
from os.path import (
    join
)


try:
    toolchain = environ["MSP430_TOOLCHAIN"]
except:
    print("""MSP430_TOOLCHAIN environment variable should point to folder \
with compiler toolchain. Ex. /home/user/msp430-gcc-7.3.2.154_linux64 """
    )
    raise

try:
    qemu = environ["MSP430_QEMU"]
except:
    print("""MSP430_QEMU environment variable should point to Qemu binaries. \
Ex. /home/user/qemu/bin/qemu-system-msp430x."""
    )


c2t_cfg = C2TConfig(
    rsp_target = DebugClient(
        march = "msp430",
        new_rsp = get_new_rsp(
            regs = list("r%d" % i for i in range(16)),
            pc = "r0",
            regsize = 16
        ),
        sp = "r1"
    ),
    qemu = DebugServer(Run(
        executable = qemu,
        args = "-M msp430f5x -S -gdb tcp:localhost:{port} -nographic "
               "-kernel {bin}"
    )),
    gdbserver = DebugServer(Run(
            executable = "/usr/bin/gdbserver",
            args = "localhost:{port} {bin}"
    )),
    target_compiler = TestBuilder(
        Run(
            executable = join(toolchain, "bin","msp430-elf-gcc"),
            args = "-nostdlib -mcpu=msp430 -g -O0 -o {bin} {src}"
        )
    ),
    oracle_compiler = TestBuilder(
        Run(
            executable = "/usr/bin/gcc",
            args = "-g -O0 -gpubnames -o {bin} {src}"
        )
    )
)