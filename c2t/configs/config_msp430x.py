# msp430g2553
# tool chain for Ubuntu 16.04:
#  sudo apt install gcc-msp430 gdb-msp430

c2t_cfg = C2TConfig(
    rsp_target = DebugClient(
        march = "msp430x",
        new_rsp = get_new_rsp(
            regs = list("r%d" % i for i in range(16)),
            pc = "r0",
            regsize = 32
        ),
        sp = "r1"
    ),
    qemu = DebugServer(Run(
        executable = "/usr/bin/qemu-system-msp430x",
        args = "-M simple -m 64k -S -gdb tcp:localhost:{port} -nographic"
    )),
    gdbserver = DebugServer(
        Run(
            executable = "/usr/bin/gdbserver",
            args = "localhost:{port} {bin}"
        )
    ),
    target_compiler = TestBuilder(
        compiler = Run(
            executable = "/usr/bin/msp430-elf-gcc",
            args = "-mcpu=msp430x -g -O0 -o {bin} {src}"
        )
    ),
    oracle_compiler = TestBuilder(
        compiler = Run(
            executable = "/usr/bin/gcc",
            args = "-g -O0 -gpubnames -o {bin} {src}"
        )
    )
)
