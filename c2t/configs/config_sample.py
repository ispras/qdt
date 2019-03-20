# If 'target' and 'oracle' have the same frontend, then uncomment, implement
# and use following:

# frontend = Run(
#     executable = "",
#     args = ""
# )

# Cpu Testing Tool configuration
c2t_cfg = C2TConfig(
    # describe RSP target for QEMU
    rsp_target = DebugClient(
        # existing RSP target name or new RSP target name
        march = "",
        # if required RSP target doesn't exist, it can be described here
        # (it is optional)
        new_rsp = get_new_rsp(
            # list of registers names
            regs = [""],
            # program register name
            pc = "",
            # register size in bits, e. g. 16, 32, 64
            regsize =
        ),
        # set the stack pointer in QEMU, if necessary
        # (value = ELF .text section address + 0x10000)
        # (it is optional)
        sp = "",
        # reset QEMU before testing, if necessary (default False)
        # (it is optional)
        qemu_reset =
    ),
    # set QEMU command line run description
    qemu = DebugServer(
        Run(
            executable = "",
            args = ""
        )
    ),
    # set gdbserver command line run description
    gdbserver = DebugServer(
        Run(
            executable = "",
            args = ""
        )
    ),
    # set command line runs description of test building for 'target'
    target_compiler = TestBuilder(
        # combination options

        ###################
        #        1        #
        ###################
        compiler = Run(
            executable = "",
            args = "",
        ),
        # linker is optional
        linker = Run(
            executable = "",
            args = ""
        )

        ###################
        #        2        #
        ###################
        frontend = Run(
            executable = "",
            args = "",
        ),
        backend = Run(
            executable = "",
            args = ""
        ),
        # linker is optional
        linker = Run(
            executable = "",
            args = ""
        )
    ),
    # set command line runs description of test building for 'oracle'
    oracle_compiler = TestBuilder(
        # combination options

        ###################
        #        1        #
        ###################
        compiler = Run(
            executable = "",
            args = "",
        ),
        # linker is optional
        linker = Run(
            executable = "",
            args = ""
        )

        ###################
        #        2        #
        ###################
        frontend = Run(
            executable = "",
            args = "",
        ),
        backend = Run(
            executable = "",
            args = ""
        ),
        # linker is optional
        linker = Run(
            executable = "",
            args = ""
        )
    )
)
