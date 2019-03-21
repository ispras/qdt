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
    listdir,
    makedirs
)
from signal import (
    SIGKILL
)
from argparse import (
    ArgumentParser,
    Action,
    ArgumentDefaultsHelpFormatter
)
from re import (
    compile,
    findall
)
from multiprocessing import (
    cpu_count,
    Process,
    Queue
)
from subprocess import (
    Popen,
    PIPE
)
from errno import (
    EEXIST
)
from platform import (
    machine
)
from collections import (
    defaultdict
)
from common import (
    pypath
)
from debug import (
    InMemoryELFFile,
    DWARFInfoCache,
    Runtime,
    get_elffile_loading
)
with pypath("pyrsp"):
    from pyrsp.rsp import (
        archmap
    )
    from pyrsp.elf import (
        ELF
    )
from c2t import (
    C2TConfig,
    Run,
    get_new_rsp,
    DebugClient,
    DebugServer,
    TestBuilder,
    DebugCommandExecutor,
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


class C2tDebugSession(Process):
    """ This class manages debugging session """

    def __init__(self, target, srcfile, port, elffile, queue, verbose):
        super(C2tDebugSession, self).__init__()
        self.rsp = target(port, elffile,
            verbose = verbose
        )
        self.port = port
        self.queue = queue
        self.reset(srcfile, elffile)

    def reset(self, srcfile, elffile):
        self.srcfile = srcfile
        self.elf = InMemoryELFFile(elffile)
        di = self.elf.get_dwarf_info()
        dic = DWARFInfoCache(di,
            symtab = self.elf.get_section_by_name(b".symtab")
        )
        self.rt = Runtime(self.rsp, dic)
        self.rsp.elf = ELF(elffile)
        self.addr2line = {}
        self.ch_line2var = defaultdict(list)
        self.chc_line2var = defaultdict(list)

    def set_br_by_line(self, lineno, cb):
        line_map = self.rt.dic.find_line_map(self.srcfile)
        line_descs = line_map[lineno]
        for desc in line_descs:
            # TODO: set a breakpoint at one address by line number?
            # if desc.state.is_stmt:
            addr = self.rt.target.reg_fmt % desc.state.address
            self.addr2line[addr] = lineno
            self.rt.add_br(addr, cb)
                # break

    def _execute_debug_comment(self):
        lineno = 1

        with open(self.srcfile, 'r') as f:
            re_comment = compile("^.*//\$(.+)$")
            re_command = compile("([^, ]+)+")
            for line in f:
                mi = re_comment.match(line)
                if mi:
                    commands = re_command.findall(mi.group(1))
                    glob = DebugCommandExecutor(locals(), lineno)
                    exec('\n'.join(commands), glob)
                lineno += 1

    @property
    def _var_size(self):
        re_size = compile("^.+_(?:u?(\d+))_.+$")
        size_str = re_size.match(basename(self.srcfile)).group(1)
        return int(size_str) / 8

    def _dump_var(self, addr, lineno, var_names):
        dump = dict(
            addr = addr,
            lineno = lineno,
            vars = dict(
                map(lambda x: (x, self.rt[x].fetch(self._var_size)),
                    var_names if var_names else self.rt
                )
            ),
            regs = self.rt.target.regs
        )
        if self.rt.target.verbose:
            print(dump.values())
        self.queue.put(dump)

    def _dump(self, addr, lineno):
        dump = dict(
            addr = addr,
            lineno = lineno,
            regs = self.rt.target.regs
        )
        if self.rt.target.verbose:
            print(dump.values())
        self.queue.put(dump)

    # debugging callbacks
    def check_cb(self):
        addr = self.rt.target.regs[self.rt.target.pc_reg]
        lineno = self.addr2line[addr]

        self._dump(addr, lineno)
        self.rt.remove_br(addr, self.check_cb)

    def cycle_check_cb(self):
        addr = self.rt.target.regs[self.rt.target.pc_reg]
        lineno = self.addr2line[addr]

        self._dump(addr, lineno)

    def check_vars_cb(self):
        addr = self.rt.target.regs[self.rt.target.pc_reg]
        lineno = self.addr2line[addr]

        var_names = self.ch_line2var.get(lineno)

        self._dump_var(addr, lineno, var_names)
        self.rt.remove_br(addr, self.check_vars_cb)

    def cycle_check_vars_cb(self):
        addr = self.rt.target.regs[self.rt.target.pc_reg]
        lineno = self.addr2line[addr]

        var_names = self.chc_line2var.get(lineno)

        self._dump_var(addr, lineno, var_names)

    def finish_cb(self):
        addr = self.rt.target.regs[self.rt.target.pc_reg]
        self.rt.remove_br(addr, self.finish_cb)
        if self.queue:
            self.queue.put("DEBUG_EXIT")
        for br in self.rt.target.br.keys()[:]:
            self.rt.target.del_br(br)
        self.rt.target.exit = True
    # end debugging callbacks

    def kill(self):
        self.rt.target.send('k')

    def detach(self):
        self.rt.target.send('D')

    def port_close(self):
        self.rt.target.port.close()


class C2tOracleSession(C2tDebugSession):

    def run(self):
        self._execute_debug_comment()
        self.rt.target.run(setpc = False)


class C2tTargetSession(C2tDebugSession):

    def load(self):
        if self.rt.target.verbose:
            print("load %s" % self.rt.target.elf.name)

        loading = get_elffile_loading(self.elf)
        for data, addr in loading:
            self.rt.target.store(data, addr)

    def run(self):
        self._execute_debug_comment()
        self.load()
        if c2t_cfg.rsp_target.sp is not None:
            self.rt.target.set_reg(c2t_cfg.rsp_target.sp,
                self.rt.target.reg_fmt % (
                    self.rt.target.elf.symbols["main"] + 0x10000
                )
            )
        self.rt.target.run(start = "main")


class ProcessWithErrCatching(Process):
    """ Process with error catching """

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


def tests_perform_nonkill(tests_queue, res_queue, verbose):
    pass


def tests_perform_kill(tests_queue, res_queue, verbose):
    pass


class C2TTestBuilder(Process):
    """ A helper class that builds tests """

    def __init__(self, tests, tests_queue, queue_min, verbose):
        super(C2TTestBuilder, self).__init__()
        self.tests = tests
        self.tests_queue = tests_queue
        self.queue_min = queue_min
        self.verbose = verbose

    def test_build(self, cmpl_unit, test_src, test_ir, test_bin):
        # TODO: do terminate in this case
        run_script = ''

        for run_script in cmpl_unit.run_script:
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
            while self.tests_queue.qsize() > self.queue_min:
                pass
            test_name = test[:-2]
            test_src = join(C2T_TEST_DIR, test)
            test_ir = join(C2T_TEST_IR_DIR, test_name)
            test_bin = join(C2T_TEST_BIN_DIR, test_name)

            oracle_elf = self.test_build(c2t_cfg.oracle_compiler, test_src,
                test_ir, test_bin + "_%s" % ORACLE_CPU
            )
            target_elf = self.test_build(c2t_cfg.target_compiler, test_src,
                test_ir, test_bin + "_%s" % c2t_cfg.rsp_target.march
            )

            self.tests_queue.put((test_src, oracle_elf,  target_elf))


def start_cpu_testing(tests, jobs, kill, verbose):
    tests_queue = Queue(0)
    tb = C2TTestBuilder(tests, tests_queue, jobs, verbose)
    tb.start()

    res_queue = Queue(0)

    if not kill:
        f = tests_perform_nonkill
    else:
        f = tests_perform_kill

    if jobs > len(tests):
        jobs = len(tests)

    performers = []
    for i in range(0, jobs):
        p = Process(
            target = f,
            args = [tests_queue, res_queue, verbose]
        )
        performers.append(p)
        p.start()

    tb.join()
    for performer in performers:
        performer.join()


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
        dest = getattr(namespace, self.dest, None)
        try:
            dest.extend([(self.metavar, values)])
        except AttributeError:
            dest = []
            setattr(namespace, self.dest, dest)
            dest.append([(self.metavar, values)])


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
        )),
        formatter_class = ArgumentDefaultsHelpFormatter
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
    parser.add_argument("-t", "--include",
        type = str,
        metavar = "RE_INCLD",
        action = Extender,
        dest = "regexps",
        default = ".*\.c",
        help = ("regular expressions to include a test set "
            "(tests are located in %s)" % C2T_TEST_DIR
        )
    )
    parser.add_argument("-s", "--exclude",
        type = str,
        metavar = "RE_EXCLD",
        action = Extender,
        dest = "regexps",
        help = ("regular expressions to exclude a test set "
            "(tests are located in %s)" % C2T_TEST_DIR
        )
    )
    parser.add_argument("-j", "--jobs",
        type = int,
        dest = "jobs",
        default = 1,
        help = ("allow N debugging jobs at once (N = [1, NCPU - 1]) "
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

    regexps = args.regexps
    if type(args.regexps) is str:
        regexps = [("RE_INCLD", ".*\.c")]
    re_var, regexp, tests = find_tests(regexps)
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
        jobs = min(jobs, cpu_count() - 1)

    # creates tests subdirectories if they don't exist
    try:
        makedirs(C2T_TEST_IR_DIR)
    except OSError as e:
        if e.errno != EEXIST:
            c2t_exit("%s creation error" % C2T_TEST_IR_DIR)
    try:
        makedirs(C2T_TEST_BIN_DIR)
    except OSError as e:
        if e.errno != EEXIST:
            c2t_exit("%s creation error" % C2T_TEST_BIN_DIR)

    start_cpu_testing(tests, jobs, args.kill, args.verbose)


if __name__ == "__main__":
    main()
