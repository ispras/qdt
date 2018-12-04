from c2t.c2t_config import *

common_frontend = Run(
    executable = "/usr/local/bin/clang",
    args = "-g -O0 -emit-llvm -c {src} -o {ir}.bc"
)

c2t_cfg = C2TConfig(
    march = "cortexm3",
    qemu = DebugUnit(Run(
        executable = "/usr/bin/qemu-system-arm",
        args = "-M versatilepb -m 128M -S -s -nographic"
    )),
    gdbserver = DebugUnit(Run(
        executable = "/usr/bin/gdbserver",
        args = "localhost:4321 {bin}"
    )),
    target_compiler = CompileUnit(
        frontend = common_frontend,
        backend = Run(
            executable = "/usr/local/bin/llc",
            args = "-O0 -march=arm -filetype=obj {ir}.bc -o {bin}.o"
        )
    ),
    oracle_compiler = CompileUnit(
        frontend = common_frontend,
        backend = Run(
            executable = "/usr/local/bin/llc",
            args = "-O0 -march=x86-64 -filetype=obj {ir}.bc -o {bin}.o"
        ),
        linker = Run(
            executable = "/usr/bin/ld",
            args = "-e main {bin}.o -o {bin}"
        )
    )
)
