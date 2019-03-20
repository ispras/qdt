# If 'target' and 'oracle' have the same frontend, then uncomment, implement
# and use following:

# frontend = Run(
#     executable = "",
#     args = ""
# )

c2t_cfg = C2TConfig(
    rsp_target = DebugClient(
        march = ""
    ),
    qemu = DebugServer(
        Run(
            executable = "",
            args = ""
        )
    ),
    gdbserver = DebugServer(
        Run(
            executable = "",
            args = ""
        )
    ),
    target_compiler = TestBuilder(
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
    oracle_compiler = TestBuilder(
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
