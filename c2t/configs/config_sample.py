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
    # symbolic values for `args` string that can be used to construct file
    # names:
    #
    # {c2t_dir} -- folder of `c2t.py`
    # {test_dir} -- path to `qdt/c2t/tests`
    #
    # {src} -- name of source file that is located in `qdt/c2t/tests`
    # {ir} -- base for intermediate file names, it has prefix
    # `qdt/c2t/tests/ir`
    # {bin} -- output binary file of compiled test, that is located in
    # `qdt/c2t/tests/bin`
    #
    # Note: one of the runs must produce {bin} file
    #
    # set command line runs description of test building for 'target'
    target_compiler = TestBuilder(
        Run(
            executable = "",
            args = "",
        ),
        Run(
            executable = "",
            args = ""
        ),
        # ...
        Run(
            executable = "",
            args = "{bin}"
        )
    ),
    # set command line runs description of test building for 'oracle'
    oracle_compiler = TestBuilder(
        Run(
            executable = "",
            args = "",
        ),
        Run(
            executable = "",
            args = ""
        ),
        # ...
        Run(
            executable = "",
            args = "{bin}"
        )
    )
)
