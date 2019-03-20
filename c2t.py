#!/usr/bin/env python
""" QEMU CPU Testing Tool """

from sys import (
    stderr
)
from os.path import (
    basename,
    dirname,
    join,
    exists
)
from os import (
    killpg,
    setpgrp
)
from signal import (
    SIGKILL
)
from argparse import (
    ArgumentParser
)
from common import (
    pypath
)
with pypath("pyrsp"):
    from pyrsp.rsp import (
        archmap
    )
from c2t import (
    C2TConfig,
    Run,
    get_new_rsp,
    DebugClient,
    DebugServer,
    TestBuilder
)

C2T_ERRMSG_FORMAT = "{prog}:\x1b[31m error:\x1b[0m {msg}\n"


def c2t_exit(msg, prog = __file__):
    print(C2T_ERRMSG_FORMAT.format(
        prog = basename(prog),
        msg = msg
    ))
    killpg(0, SIGKILL)


C2T_DIR = dirname(__file__) or '.'
C2T_CONFIGS_DIR = join(C2T_DIR, "c2t", "configs")

c2t_cfg = None


def verify_config_components(config):
    if c2t_cfg.rsp_target.rsp is None:
        c2t_exit("unsupported GDB RSP target: %s" % c2t_cfg.rsp_target.march,
            prog = config
        )

    errmsg1 = "compiler specified with frontend or backend"
    errmsg2 = "frontend or backend are not specified"

    if c2t_cfg.target_compiler.compiler is not None:
        if (    c2t_cfg.target_compiler.frontend is not None
            or  c2t_cfg.target_compiler.backend is not None
        ):
            c2t_exit(errmsg1, prog = "%s: target_compiler" % config)
    elif (    c2t_cfg.target_compiler.frontend is None
          or  c2t_cfg.target_compiler.backend is None
    ):
        c2t_exit(errmsg2, prog = "%s: target_compiler" % config)

    if c2t_cfg.oracle_compiler.compiler is not None:
        if (    c2t_cfg.oracle_compiler.frontend is not None
            or  c2t_cfg.oracle_compiler.backend is not None
        ):
            c2t_exit(errmsg1, prog = "%s: oracle_compiler" % config)
    elif (    c2t_cfg.oracle_compiler.frontend is None
          or  c2t_cfg.oracle_compiler.backend is None
    ):
        c2t_exit(errmsg2, prog = "%s: oracle_compiler" % config)


class C2TArgumentParser(ArgumentParser):
    """ ArgumentParser with custom error method """

    def error(self, msg):
        self.print_usage(stderr)
        self.exit(2, C2T_ERRMSG_FORMAT.format(
            prog = self.prog,
            msg = msg
        ))


def main():
    setpgrp()

    parser = C2TArgumentParser(
        description = "QEMU CPU Testing Tool",
        epilog = ("supported GDB RSP targets: {rsp}".format(
            rsp = ', '.join(archmap.keys())
        ))
    )
    parser.add_argument(
        type = str,
        dest = "config",
        help = ("configuration file for {prog} (see sample and examples in "
            "{dir})".format(
                prog = parser.prog,
                dir = C2T_CONFIGS_DIR
            )
        )
    )

    args = parser.parse_args()

    config = args.config
    if not exists(config):
        cfg_file = "%s.py" % config if not config.endswith(".py") else config
        config = join(C2T_CONFIGS_DIR, cfg_file)
        if not exists(config):
            config = join(C2T_DIR, cfg_file)
            if not exists(config):
                parser.error(
                    "configuration file doesn't exist: {config}".format(
                        config = args.config
                    )
                )

    glob = {
        "C2TConfig": C2TConfig,
        "Run": Run,
        "get_new_rsp": get_new_rsp,
        "DebugClient": DebugClient,
        "DebugServer": DebugServer,
        "TestBuilder": TestBuilder
    }

    # getting `c2t_cfg` configuration for cpu testing tool
    try:
        execfile(config, glob)
    except Exception as e:
        c2t_exit(e, prog = config)
    else:
        global c2t_cfg
        for val in glob.values():
            if isinstance(val, C2TConfig):
                c2t_cfg = val
                break
        if c2t_cfg is None:
            c2t_exit(("`c2t_cfg` not found (see sample and examples in "
                    "{dir})".format(dir = C2T_CONFIGS_DIR)
                ),
                prog = config
            )
    verify_config_components(config)


if __name__ == "__main__":
    main()
