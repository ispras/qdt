from c2t.c2t_config import *

# msp430g2553

c2t_cfg = C2TConfig(
    march = "msp430x",
    qemu = DebugUnit(Run(
        executable = "/home/real/work/qemu/debug/bin/qemu-system-msp430x",
        args = "-M none -m 64k -S -gdb tcp:localhost:{port} -nographic"
    )),
    gdbserver = DebugUnit(
        Run(
            executable = "/usr/bin/gdbserver",
            args = "localhost:{port} {bin}"
        ),
        gdb_target = rsp_target(
            regs = list("r%d" for i in range(16)),
            pc = "r0",
            regsize = 20,
            little_endian = True
        )
    ),
    target_compiler = CompileUnit(
        compiler = Run(
            executable = "/usr/bin/msp430-gcc",
            args = "-mmcu=msp430g2553 -g -O0 -o {bin} {src}"
        )
    ),
    oracle_compiler = CompileUnit(
        compiler = Run(
            executable = "/usr/bin/gcc",
            args = "-g -O0 -gpubnames -o {bin} {src}"
        )
    )
)
