c2t_cfg = C2TConfig(
    rsp_target = DebugClient(
        march = "r4000",
        new_rsp = get_new_rsp(
            regs = ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9",
                "r10", "r11", "r12", "r13", "r14", "r15", "r16", "r17", "r18",
                "r19", "r20", "r21", "r22", "r23", "r24", "r25", "r26", "r27",
                "r28", "r29", "r30", "r31", "status", "lo", "hi", "badvaddr",
                "cause", "pc", "f0", "f1", "f2", "f3", "f4", "f5", "f6", "f7",
                "f8", "f9", "f10", "f11", "f12", "f13", "f14", "f15", "f16",
                "f17", "f18", "f19", "f20", "f21", "f22", "f23", "f24", "f25",
                "f26", "f27", "f28", "f29", "f30", "f31", "fcsr", "fir",
                "restart"],
            pc = "pc",
            regsize = 32
        ),
        test_timeout = 20.,
        sp = "r29"
    ),
    qemu = DebugServer(Run(
        executable = "/usr/bin/qemu-system-mipsel",
        args = ("-m 256 -M mips -kernel {bin} -S "
            "-gdb tcp:localhost:{port} -nographic"
        )
    )),
    gdbserver = DebugServer(Run(
        executable = "/usr/bin/gdbserver",
        args = "localhost:{port} {bin}"
    )),
    target_compiler = TestBuilder(
        Run( # compiler
            executable = "/usr/bin/mipsel-linux-gnu-gcc",
            args = "-g -O0 -march=r4000 {src} -o {bin}"
        )
    ),
    oracle_compiler = TestBuilder(
        Run( # compiler
            executable = "/usr/bin/gcc",
            args = "-g -O0 {src} -o {bin}"
        )
    )
)
