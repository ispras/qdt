c2t_cfg = C2TConfig(
    rsp_target = DebugClient(
        march = "cortexm3",
        qemu_reset = True
    ),
    qemu = DebugServer(Run(
        executable = "/usr/bin/qemu-system-arm",
        args = ("-M netduino2 -cpu cortex-m3 -kernel {bin} -S "
            "-gdb tcp:localhost:{port} -nographic"
        )
    )),
    gdbserver = DebugServer(Run(
        executable = "/usr/bin/gdbserver",
        args = "localhost:{port} {bin}"
    )),
    target_compiler = TestBuilder(
        compiler = Run(
            executable = "/usr/bin/arm-none-eabi-gcc",
            args = ("-DTEST -mno-unaligned-access -g -Wall -O0 "
                "-mfix-cortex-m3-ldrd -msoft-float -mthumb "
                "-Wno-strict-aliasing -fomit-frame-pointer -mcpu=cortex-m3 "
                "-c {src} -o {bin}.o"
            )
        ),
        linker = Run(
            executable = "/usr/bin/arm-none-eabi-gcc",
            args = ("-mthumb -mcpu=cortex-m3 -fno-common "
                "-T {c2t_test_dir}/misc/cortexm3_memmap -nostartfiles "
                "-Wl,--gc-sections -Wl,-z,relro {bin}.o -o {bin}"
            )
        )
    ),
    oracle_compiler = TestBuilder(
        compiler = Run(
            executable = "/usr/bin/gcc",
            args = "-g -O0 {src} -o {bin}"
        )
    )
)
