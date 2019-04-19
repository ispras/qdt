common_frontend = Run(
    executable = "/usr/local/bin/clang",
    args = "-g -O0 -emit-llvm -c {src} -o {ir}.bc"
)

c2t_cfg = C2TConfig(
    rsp_target = DebugClient(
        march = "arm926",
        new_rsp = get_new_rsp(
            regs = ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8",
                "r9", "r10", "r11", "r12", "sp", "lr", "pc",
                "xpsr", "msp", "psp", "special"],
            pc = "pc",
            regsize = 32
        ),
        sp = "sp"
    ),
    qemu = DebugServer(Run(
        executable = "/usr/bin/qemu-system-arm",
        args = ("-M versatilepb -cpu arm926 -m 128M -S "
            "-gdb tcp:localhost:{port} -nographic"
        )
    )),
    gdbserver = DebugServer(Run(
        executable = "/usr/bin/gdbserver",
        args = "localhost:{port} {bin}"
    )),
    target_compiler = TestBuilder(
        common_frontend,
        Run( # backend
            executable = "/usr/local/bin/llc",
            args = ("-O0 -march=arm -mcpu=arm926ej-s -filetype=obj {ir}.bc -o "
                "{bin}"
            )
        )
    ),
    oracle_compiler = TestBuilder(
        common_frontend,
        Run( # backend
            executable = "/usr/local/bin/llc",
            args = "-O0 -march=x86-64 -filetype=obj {ir}.bc -o {ir}.o"
        ),
        Run( # linker
            executable = "/usr/bin/ld",
            args = "-e main {ir}.o -o {bin}"
        )
    )
)
