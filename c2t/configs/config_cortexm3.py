c2t_cfg = C2TConfig(
    rsp_target = DebugClient(
        march = "cortexm3",
        qemu_reset = True,
        sp = "sp"
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
        Run( # compiler
            executable = "/usr/bin/arm-none-eabi-gcc",
            args = ("-DTEST -mno-unaligned-access -g -Wall -O0 "
                "-mfix-cortex-m3-ldrd -msoft-float -mthumb "
                "-Wno-strict-aliasing -fomit-frame-pointer -mcpu=cortex-m3 "
                "-c {src} -o {ir}.o"
            )
        ),
        Run( # linker
            executable = "/usr/bin/arm-none-eabi-gcc",
            args = ("-mthumb -mcpu=cortex-m3 -fno-common "
                "-T {test_dir}/misc/cortexm3_memmap -nostartfiles "
                "-Wl,--gc-sections -Wl,-z,relro {ir}.o -o {bin}"
            )
        ),
        Run( # dissassembler
            executable = "/usr/bin/arm-none-eabi-gcc",
            args = ("-DTEST -mno-unaligned-access -g -Wall -O0 "
                "-mfix-cortex-m3-ldrd -msoft-float -mthumb "
                "-Wno-strict-aliasing -fomit-frame-pointer -mcpu=cortex-m3 "
                "-c {src} -Wa,-adhln > {ir}.disas"
            )
        )
    ),
    oracle_compiler = TestBuilder(
        Run( # compiler
            executable = "/usr/bin/gcc",
            args = "-g -O0 {src} -o {bin}"
        )
    )
)
