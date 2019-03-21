#!/usr/bin/env python
""" QEMU CPU Testing Tool """

from sys import (
    stderr
)
from os.path import (
    dirname,
    join,
    exists,
    basename
)
from os import (
    listdir,
    killpg,
    setpgrp
)
from signal import (
    SIGKILL
)
from argparse import (
    Action,
    ArgumentDefaultsHelpFormatter,
    ArgumentParser
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


class Extender(Action):

    def __call__(self, parser, namespace, values, option_strings = None):
        dest = getattr(namespace, self.dest, self.default)
        if dest is self.default:
            setattr(namespace, self.dest, [(self.metavar, values)])
        else:
            dest.append((self.metavar, values))


def verify_config_components(config):
    if c2t_cfg.rsp_target.rsp is None:
        c2t_exit("unsupported GDB RSP target: %s" % c2t_cfg.rsp_target.march,
            prog = config
        )

    for compiler, compiler_name in (
        (c2t_cfg.target_compiler, "target_compiler"),
        (c2t_cfg.oracle_compiler, "oracle_compiler")
    ):
        if not any((compiler.compiler, compiler.frontend, compiler.backend)):
            c2t_exit("%s is not specified" % compiler_name, prog = config)
        else:
            if compiler.compiler:
                if compiler.frontend or compiler.backend:
                    msg = "compiler specified with %s" % (
                        "frontend" if compiler.frontend else "backend"
                    )
                    c2t_exit(msg, prog = "%s: %s" % (config, compiler_name))
            else:
                if not compiler.frontend or not compiler.backend:
                    msg = "%s is not specified" % (
                        "frontend" if not compiler.frontend else "backend"
                    )
                    c2t_exit(msg, prog = "%s: %s" % (config, compiler_name))


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
        )),
        formatter_class = ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("config",
        type = str,
        help = ("configuration file for {prog} (see sample and examples in "
            "{dir})".format(
                prog = parser.prog,
                dir = C2T_CONFIGS_DIR
            )
        )
    )
    DEFAULT_REGEXPS = (("RE_INCLD", ".*\.c"),)
    parser.add_argument("-t", "--include",
        type = str,
        metavar = "RE_INCLD",
        action = Extender,
        dest = "regexps",
        default = DEFAULT_REGEXPS,
        help = ("regular expressions to include a test set "
            "(tests are located in %s)" % C2T_TEST_DIR
        )
    )
    parser.add_argument("-s", "--exclude",
        type = str,
        metavar = "RE_EXCLD",
        action = Extender,
        dest = "regexps",
        default = DEFAULT_REGEXPS,
        help = ("regular expressions to exclude a test set "
            "(tests are located in %s)" % C2T_TEST_DIR
        )
    )
    parser.add_argument("-j", "--jobs",
        type = int,
        dest = "jobs",
        default = 1,
        help = ("allow N debugging jobs at once (N = [1, NCPU]) "
                "(default N = 1)"
        )
    )

    args = parser.parse_args()

    config = args.config
    cfg_file = "%s.py" % config if not config.endswith(".py") else config

    config = cfg_file
    if not exists(config):
        config = join(C2T_CONFIGS_DIR, cfg_file)
        if not exists(config):
            config = join(C2T_DIR, cfg_file)
            if not exists(config):
                parser.error(
                    "configuration file doesn't exist: " + args.config
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

    re_var, regexp, tests = find_tests(args.regexps)
    if not tests:
        parser.error("no matches in {dir} with: {var} = '{regexp}'".format(
            dir = C2T_TEST_DIR,
            var = re_var,
            regexp = regexp
        ))

    jobs = args.jobs
    if jobs < 1:
        parser.error("wrong number of jobs: %s" % jobs)
    else:
        jobs = min(jobs, cpu_count())


if __name__ == "__main__":
    main()
