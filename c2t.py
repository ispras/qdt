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
    makedirs,
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
    findall,
    compile
)
from multiprocessing import (
    Process,
    cpu_count
)
from subprocess import (
    Popen,
    PIPE
)
from platform import (
    machine
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
C2T_TEST_IR_DIR = join(C2T_TEST_DIR, "ir")
C2T_TEST_BIN_DIR = join(C2T_TEST_DIR, "bin")

ORACLE_CPU = machine()

c2t_cfg = None


class ProcessWithErrCatching(Process):

    def __init__(self, command):
        Process.__init__(self)
        self.cmd = command
        self.prog = command.split(' ')[0]

    def run(self):
        process = Popen(self.cmd,
            shell = True,
            stdout = PIPE,
            stderr = PIPE
        )
        _, err = process.communicate()
        if process.returncode != 0:
            c2t_exit(err, prog = self.prog)


class C2TTestBuilder(Process):
    """ A helper class that builds tests """

    def __init__(self, compiler, tests, tests_tail, tests_queue, verbose):
        super(C2TTestBuilder, self).__init__()
        self.compiler = compiler
        self.tests = tests
        self.tests_tail = tests_tail
        self.tests_queue = tests_queue
        self.verbose = verbose

    def test_build(self, test_src, test_ir, test_bin):
        for run_script in self.compiler.run_script:
            cmd = run_script.format(
                src = test_src,
                ir = test_ir,
                bin = test_bin,
                c2t_dir = C2T_DIR,
                c2t_test_dir = C2T_TEST_DIR
            )
            if self.verbose:
                print(cmd)
            cmpl_unit = ProcessWithErrCatching(cmd)
            cmpl_unit.start()
            cmpl_unit.join()

        ext = findall("-o {bin}(\S*)", run_script).pop()
        return test_bin + ext

    def run(self):
        for test in self.tests:
            test_name = test[:-2]
            test_src = join(C2T_TEST_DIR, test)
            test_ir = join(C2T_TEST_IR_DIR, test_name)
            test_bin = join(C2T_TEST_BIN_DIR, test_name)

            test_elf = self.test_build(test_src, test_ir,
                test_bin + "_%s" % self.tests_tail
            )

            self.tests_queue.put((test_src, test_elf))


def start_cpu_testing(tests, jobs, kill, verbose):
    pass


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
    parser.add_argument("-k", "--kill",
        action = "store_true",
        help = "kill debug servers after each test (now only QEMU)"
    )
    parser.add_argument("-v", "--verbose",
        action = "store_true",
        help = "increase output verbosity"
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

    # creates tests subdirectories if they don't exist
    for sub_dir in (C2T_TEST_IR_DIR, C2T_TEST_BIN_DIR):
        if not exists(sub_dir):
            makedirs(sub_dir)

    start_cpu_testing(tests, jobs, args.kill, args.verbose)


if __name__ == "__main__":
    main()
