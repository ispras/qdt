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
    setpgrp,
    listdir
)
from signal import (
    SIGKILL
)
from argparse import (
    ArgumentParser,
    Action
)
from re import (
    compile
)
from multiprocessing import (
    cpu_count
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
C2T_TEST_DIR = join(C2T_DIR, "c2t", "tests")

c2t_cfg = None


def find_tests(regexps):
    tests = listdir(C2T_TEST_DIR)

    for re_type, regexp in regexps:
        r = compile(regexp)
        if re_type == "RE_INCLD":
                tests = filter(r.match, tests)
        else:
            for test in filter(r.match, tests):
                tests.remove(test)
        if not tests:
            break
    return re_type, regexp, tests


# https://stackoverflow.com/questions/12460989/argparse-how-can-i-allow-
# multiple-values-to-override-a-default
class Extender(Action):

    def __call__(self, parser, namespace, values, option_strings = None):
        dest = getattr(namespace, self.dest, None)
        if not hasattr(dest, "extend") or dest == self.default:
            dest = []
            setattr(namespace, self.dest, dest)
            parser.set_defaults(**{self.dest: None})

        if not values:
            values = [""]

        try:
            dest.extend(map(lambda x: (self.metavar, x), values))
        except ValueError:
            dest.append(map(lambda x: (self.metavar, x), values))


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
    parser.add_argument("-c", "--config",
        type = str,
        dest = "config",
        help = ("configuration file for {prog} (see sample and examples in "
            "{dir})".format(
                prog = parser.prog,
                dir = C2T_CONFIGS_DIR
            )
        )
    )
    parser.add_argument("-t", "--include",
        type = str,
        nargs = '*',
        metavar = "RE_INCLD",
        action = Extender,
        dest = "regexps",
        default = [("RE_INCLD", ".*\.c")],
        help = (("regular expressions to include a test set "
            "(tests are located in {dir}) (default value = '.*\.c')".format(
                dir = C2T_TEST_DIR
            )
        ))
    )
    parser.add_argument("-s", "--exclude",
        type = str,
        nargs = '*',
        metavar = "RE_EXCLD",
        action = Extender,
        dest = "regexps",
        help = (("regular expressions to exclude a test set "
            "(tests are located in {dir})".format(dir = C2T_TEST_DIR)
        ))
    )
    parser.add_argument("-j", "--jobs",
        type = int,
        dest = "jobs",
        default = 1,
        help = ("allow N debugging jobs at once (N = [1, NCPU - 1]) "
                "(default N = 1)"
        )
    )

    args = parser.parse_args()

    if not args.config:
        parser.error("requires more input arguments to run")

    config = args.config
    if not exists(config):
        config_name = ("%s.py" % args.config if not args.config.endswith(".py")
            else args.config
        )
        config = join(C2T_CONFIGS_DIR, config_name)
        if not exists(config):
            config = join(C2T_DIR, config_name)
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
    proxy = {}

    # getting `c2t_cfg` configuration for cpu testing tool
    try:
        execfile(config, glob, proxy)
    except Exception as e:
        c2t_exit(e, prog = config)
    else:
        global c2t_cfg
        c2t_cfg = proxy.get("c2t_cfg")
        if c2t_cfg is None:
            c2t_exit(("`c2t_cfg` not found (see `config_sample.py` and "
                    "examples in {dir})".format(dir = C2T_CONFIGS_DIR)
                ),
                prog = config
            )
    verify_config_components(config)

    re_var, regexp, tests = find_tests(args.regexps)
    if not tests:
        parser.error("no matches in {dir} with: {var} = '{regexp}'".format(
            dir = C2T_TEST_DIR,
            var = re_var,
            regexp = regexp
        ))

    if args.jobs < 1:
        parser.error("wrong number of jobs: {jobs}".format(jobs = args.jobs))
    else:
        max_jobs = cpu_count() - 1
        if args.jobs > max_jobs:
            args.jobs = max_jobs


if __name__ == "__main__":
    main()
