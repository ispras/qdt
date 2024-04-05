from os.path import (
    isfile,
)


@edef
def C2T_QEMU_SYSTEM_ARM():
    "Qemu full system emulator for ARM to be tested"
    if isfile("/usr/bin/qemu-system-arm"):
        return "/usr/bin/qemu-system-arm"
    raise Exception("No qemu-system-arm found")

@edef
def C2T_ARM_NO_EABI_GCC():
    "GCC ARM cross compiler to generate target executables"
    if isfile("/usr/bin/arm-none-eabi-gcc"):
        return "/usr/bin/arm-none-eabi-gcc"
    raise Exception("No GCC ARM cross compiler found")

@edef
def C2T_GDBSERVER():
    "A GDB RSP server to launch host executables"
    if isfile("/usr/bin/gdbserver"):
        return "/usr/bin/gdbserver"
    raise Exception("No gdbserver found")

@edef
def C2T_GCC():
    "GCC to generate host executables"
    if isfile("/usr/bin/gcc"):
        return "/usr/bin/gcc"
    raise Exception("No host targeted GCC found")


c2t_cfg = C2TConfig(
    rsp_target = DebugClient(
        march = "cortexm3",
        qemu_reset = True,
        sp = "sp"
    ),
    qemu = DebugServer(Run(
        executable = C2T_QEMU_SYSTEM_ARM,
        args = ("-M netduino2 -cpu cortex-m3 -kernel {bin} -S "
            "-gdb tcp:localhost:{port} -nographic"
        )
    )),
    gdbserver = DebugServer(Run(
        executable = C2T_GDBSERVER,
        args = "localhost:{port} {bin}"
    )),
    target_compiler = TestBuilder(
        Run( # compiler
            executable = C2T_ARM_NO_EABI_GCC,
            args = ("-DTEST -mno-unaligned-access -g -Wall -O0 "
                "-mfix-cortex-m3-ldrd -msoft-float -mthumb "
                "-Wno-strict-aliasing -fomit-frame-pointer -mcpu=cortex-m3 "
                "-c {src} -o {ir}.o"
            )
        ),
        Run( # linker
            executable = C2T_ARM_NO_EABI_GCC,
            args = ("-mthumb -mcpu=cortex-m3 -fno-common "
                "-T {test_dir}/misc/cortexm3_memmap -nostartfiles "
                "-Wl,--gc-sections -Wl,-z,relro {ir}.o -o {bin}"
            )
        ),
        Run( # dissassembler
            executable = C2T_ARM_NO_EABI_GCC,
            args = ("-DTEST -mno-unaligned-access -g -Wall -O0 "
                "-mfix-cortex-m3-ldrd -msoft-float -mthumb "
                "-Wno-strict-aliasing -fomit-frame-pointer -mcpu=cortex-m3 "
                "-c {src} -Wa,-adhln > {ir}.disas"
            )
        )
    ),
    oracle_compiler = TestBuilder(
        Run( # compiler
            executable = C2T_GCC,
            args = "-g -O0 {src} -o {bin} -no-pie"
        )
    )
)
