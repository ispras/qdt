from c2t.c2t_config import *

# If 'target' and 'oracle' have the same frontend, then uncomment, implement
# and use following:

# frontend = Run(
#     executable = "",
#     args = ""
# )

c2t_cfg = C2TConfig(
    march = "",
    qemu = DebugUnit(
        Run(
            executable = "",
            args = ""
        )
    ),
    gdbserver = DebugUnit(
        Run(
            executable = "",
            args = ""
        )
    ),
    target_compiler = CompileUnit(
        # just one of '1' must be defined and '2' can be defined or not

        #        1         #
        compiler = Run(
            executable = "",
            args = "",
        ),
        #        1         #
        frontend = Run(
            executable = "",
            args = "",
        ),
        backend = Run(
            executable = "",
            args = ""
        ),
        #        2         #
        linker = Run(
            executable = "",
            args = ""
        )
    ),
    oracle_compiler = CompileUnit(
        # just one of '1' must be defined and '2' can be defined or not

        #        1         #
        compiler = Run(
            executable = "",
            args = "",
        ),
        #        1         #
        frontend = Run(
            executable = "",
            args = "",
        ),
        backend = Run(
            executable = "",
            args = ""
        ),
        #        2         #
        linker = Run(
            executable = "",
            args = ""
        )
    )
)
