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
    makedirs
)
from signal import (
    SIGKILL,
    SIGTERM
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
    Queue,
    Lock
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
from struct import (
    pack
)
from common import (
    filefilter,
    cli_repr,
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
    from pyrsp.utils import (
        find_free_port,
        wait_for_tcp_port,
        QMP
    )
from c2t import (
    C2TConfig,
    Run,
    get_new_rsp,
    DebugClient,
    DebugServer,
    TestBuilder,
    DebugCommandExecutor,
    DebugComparison
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


lock = Lock()


def free_ports(start = 4321):
    while True:
        with lock:
            free = find_free_port(start)
            yield free
            start = free + 1
            # TODO: overflow 0x10000


port_pool = free_ports()


# TODO: not kill gdbserver
def tests_perform_nonkill(tests_queue, res_queue, verbose):
    test_src, oracle_elf, target_elf = tests_queue.get(block = True)

    qemu_port = next(port_pool)
    qmp_port = next(port_pool)

    qmp_run = " -qmp tcp:localhost:{port},server,nowait"
    qemu_run = (c2t_cfg.qemu.run_script.format(
        port = qemu_port,
        bin = target_elf,
        c2t_dir = C2T_DIR,
        c2t_test_dir = C2T_TEST_DIR
    ) + qmp_run.format(port = qmp_port))
    qemu = ProcessWithErrCatching(qemu_run)

    qemu.daemon = True
    qemu.start()

    # TODO: add support for port setting from config
    if not wait_for_tcp_port(qemu_port) or not wait_for_tcp_port(qmp_port):
        c2t_exit("QEMU malfunction")

    qmp = QMP(qmp_port)

    oracle_queue = Queue(0)
    target_queue = Queue(0)

    target_session = C2tTargetSession(c2t_cfg.rsp_target.rsp, test_src,
        str(qemu_port), target_elf, target_queue, verbose
    )

    if c2t_cfg.rsp_target.qemu_reset:
        target_session.rt.target[4] = pack("<I",
            target_session.rt.target.elf.entry
        )
        qmp("system_reset")

    target_session.start()

    while 1:
        gdbserver_port = next(port_pool)

        gdbserver = ProcessWithErrCatching(
            c2t_cfg.gdbserver.run_script.format(
                port = gdbserver_port,
                bin = oracle_elf,
                c2t_dir = C2T_DIR,
                c2t_test_dir = C2T_TEST_DIR
            )
        )

        gdbserver.daemon = True
        gdbserver.start()

        if not wait_for_tcp_port(gdbserver_port):
            c2t_exit("gdbserver malfunction")

        oracle_session = C2tOracleSession(archmap[ORACLE_CPU], test_src,
            str(gdbserver_port), oracle_elf, oracle_queue, verbose
        )

        oracle_session.start()

        while 1:
            oracle_dump = oracle_queue.get(block = True)
            target_dump = target_queue.get(block = True)
            if oracle_dump != "DEBUG_EXIT" and target_dump != "DEBUG_EXIT":
                dump = dict(
                    test = test_src,
                    oracle = (oracle_elf, oracle_dump),
                    target = (target_elf, target_dump)
                )
                res_queue.put(dump)
            else:
                dump = dict(TEST_END = test_src)
                res_queue.put(dump)
                break

        oracle_session.join()
        target_session.join()
        oracle_session.kill()
        gdbserver.join()
        oracle_session.port_close()

        if tests_queue.empty():
            break

        test_src, oracle_elf, target_elf = tests_queue.get(block = True)

        qmp("stop")
        qmp("system_reset")

        target_session.reset(test_src, target_elf)
        target_session.run()

    target_session.kill()
    qemu.join()
    target_session.port_close()
    res_queue.put("CMP_EXIT")


def tests_perform_kill(tests_queue, res_queue, verbose):
    oracle_queue = Queue(0)
    target_queue = Queue(0)

    while 1:
        test_src, oracle_elf, target_elf = tests_queue.get(block = True)

        qemu_port = next(port_pool)
        qmp_port = next(port_pool)
        gdbserver_port = next(port_pool)

        qmp_run = " -qmp tcp:localhost:{port},server,nowait"
        qemu = ProcessWithErrCatching(
            c2t_cfg.qemu.run_script.format(
                port = qemu_port,
                bin = target_elf,
                c2t_dir = C2T_DIR,
                c2t_test_dir = C2T_TEST_DIR
            ) + qmp_run.format(port = qmp_port)
        )
        gdbserver = ProcessWithErrCatching(
            c2t_cfg.gdbserver.run_script.format(
                port = gdbserver_port,
                bin = oracle_elf,
                c2t_dir = C2T_DIR,
                c2t_test_dir = C2T_TEST_DIR
            )
        )

        qemu.daemon = True
        gdbserver.daemon = True

        qemu.start()
        gdbserver.start()

        # TODO: add support for port setting from config
        if (    not wait_for_tcp_port(qemu_port)
            and not wait_for_tcp_port(qmp_port)
        ):
            c2t_exit("QEMU malfunction")
        if not wait_for_tcp_port(gdbserver_port):
            c2t_exit("gdbserver malfunction")

        qmp = QMP(qmp_port)

        target_session = C2tTargetSession(c2t_cfg.rsp_target.rsp, test_src,
            str(qemu_port), target_elf, target_queue, verbose
        )
        oracle_session = C2tOracleSession(archmap[ORACLE_CPU], test_src,
            str(gdbserver_port), oracle_elf, oracle_queue, verbose
        )

        if c2t_cfg.rsp_target.qemu_reset:
            target_session.rt.target[4] = pack("<I",
                target_session.rt.target.elf.entry
            )
            qmp("system_reset")

        oracle_session.start()
        target_session.start()

        while 1:
            oracle_dump = oracle_queue.get(block = True)
            target_dump = target_queue.get(block = True)
            if (    oracle_dump != "DEBUG_EXIT"
                and target_dump != "DEBUG_EXIT"):
                dump = dict(
                    test = test_src,
                    oracle = (oracle_elf, oracle_dump),
                    target = (target_elf, target_dump)
                )
                res_queue.put(dump)
            else:
                dump = dict(TEST_END = test_src)
                res_queue.put(dump)
                break

        oracle_session.join()
        target_session.join()
        oracle_session.kill()
        target_session.kill()
        qemu.join()
        gdbserver.join()
        oracle_session.port_close()
        target_session.port_close()

        if tests_queue.empty():
            break

    res_queue.put("CMP_EXIT")


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

    dc = DebugComparison(res_queue, jobs)
    try:
        dc.start()
    except RuntimeError:
        killpg(0, SIGKILL)

    tb.join()
    for performer in performers:
        performer.join()


class testfilter(filefilter):

    def __str__(self):
        res = []
        for inclusive, pattern in self:
            res.append(("-t " if inclusive else "-s ") + cli_repr(pattern))
        return " ".join(res)


class TestfilterCLI(Action):

    def __call__(self, parser, namespace, values, option_strings = None):
        dest = getattr(namespace, self.dest, self.default)
        val = (getattr(dest, self.metavar), values)
        if dest is self.default:
            setattr(namespace, self.dest, testfilter([val]))
        else:
            dest.append(val)


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
    parser.add_argument("config",
        type = str,
        help = ("configuration file for {prog} (see sample and examples in "
            "{dir})".format(
                prog = parser.prog,
                dir = C2T_CONFIGS_DIR
            )
        )
    )
    DEFAULT_REGEXPS = testfilter([(testfilter.RE_INCLD, ".*\.c"),])
    parser.add_argument("-t", "--include",
        type = str,
        metavar = "RE_INCLD",
        action = TestfilterCLI,
        dest = "regexps",
        default = DEFAULT_REGEXPS,
        help = ("regular expressions to include a test set "
            "(tests are located in %s)" % C2T_TEST_DIR
        )
    )
    parser.add_argument("-s", "--exclude",
        type = str,
        metavar = "RE_EXCLD",
        action = TestfilterCLI,
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
        help = "allow N debugging jobs at once (N = [1, NCPU - 1])"
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

    incl, regexp, tests = args.regexps.find_tests(C2T_TEST_DIR)
    if not tests:
        parser.error("no matches in {dir} with {var} {regexp}".format(
            dir = C2T_TEST_DIR,
            var = "inclusive" if incl else "exclusive",
            regexp = cli_repr(regexp)
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
    # TODO: delete it
    killpg(0, SIGTERM)


if __name__ == "__main__":
    main()
