#!/usr/bin/env python
""" QEMU CPU Testing Tool """

from c2t import (
    C2TConfig,
    config as config_api,
    DebugCommandExecutor,
    DebugComparator,
)
from common import (
    bstr,
    cli_repr,
    execfile,
    filefilter,
    HelpFormatter,
    makedirs,
    pypath,
    qdtdirs,
)
from debug import (
    DWARFInfoCache,
    get_elffile_loading,
    InMemoryELFFile,
    Runtime,
)
with pypath("pyrsp"):
    from pyrsp.rsp import (
        archmap,
    )
    from pyrsp.utils import (
        find_free_port,
        QMP,
        wait_for_tcp_port,
    )

from argparse import (
    Action,
    ArgumentParser,
)
from collections import (
    defaultdict,
)
from multiprocessing import (
    Process,
    Queue,
    Value,
)
from os import (
    killpg,
    setpgrp,
)
from os.path import (
    basename,
    dirname,
    exists,
    getmtime,
    join,
    relpath,
)
from platform import (
    machine,
)
from psutil import (
    NoSuchProcess,
    Process as psutil_Process,
)
from re import (
    compile,
)
from signal import (
    SIGKILL,
    SIGTERM,
)
from six.moves.queue import (
    Empty,
)
from struct import (
    pack,
)
from subprocess import (
    PIPE,
    Popen,
)
from sys import (
    stderr,
)
from threading import (
    Thread,
)
from time import (
    localtime,
    strftime,
)
from traceback import (
    print_exc,
)


C2T_ERRMSG_FORMAT = "{prog}:\x1b[31m error:\x1b[0m {msg}\n"


def c2t_exit(msg, prog = __file__):
    print(C2T_ERRMSG_FORMAT.format(
        prog = basename(prog),
        msg = msg.decode(),
    ))
    killpg(0, SIGKILL)


C2T_DIR = dirname(__file__) or '.'
C2T_CONFIGS_DIR = join(C2T_DIR, "c2t", "configs")
C2T_TEST_DIR = join(C2T_DIR, "c2t", "tests")
C2T_WORK_DIR = join(qdtdirs.user_cache_dir, "c2t")
C2T_LOG_TIME_FMT = "%Y.%m.%d_%H-%M-%S"

ORACLE_CPU = machine()

c2t_cfg = None


class DebugSession(object):
    """ This class manages debugging session """

    def __init__(self, target, srcfile, port, elffile, queue, verbose):
        super(DebugSession, self).__init__()
        self.rsp = target(port, verbose = verbose)
        self.port = port
        self.queue = queue
        self.reset(srcfile, elffile)
        self.session_type = None
        self.verbose = verbose

    def run(self, timeout):
        """ Run the testing through the debug session.

:returns: was timeout expired
        """
        # RSP.run is blocking. Running it in a dedicated thread allows to
        # stop it after a timeout.

        t = Thread(
            name = "RSP-" + self.session_type + "-" + str(self.port),
            target = self.thread_main
        )

        self._handling_timeout = False

        t.start()
        t.join(timeout = timeout)

        timeout_expired = t.is_alive()

        if timeout_expired:
            self._handling_timeout = True
            # Closing the socket will result in `RSP.run` failure in the
            # `t`hread soon.
            self.port_close()
            t.join()

            self._handling_timeout = False

        return timeout_expired

    def thread_main(self):
        queue = self.queue
        queue.put((self.session_type, self.srcfile, "TEST_RUN"))
        try:
            self.main()
        except:
            if self._handling_timeout:
                queue.put((self.session_type, self.srcfile, "TEST_TIMEOUT"))
            else:
                # TODO: pass session error to `queue`
                print_exc()
        else:
            queue.put((self.session_type, self.srcfile, "TEST_END"))

    def reset(self, srcfile, elffile):
        self.srcfile = srcfile
        self.elffile = elffile
        self.elf = InMemoryELFFile(elffile)
        di = self.elf.get_dwarf_info()
        dic = DWARFInfoCache(di,
            symtab = self.elf.get_section_by_name(".symtab")
        )
        if dic.aranges is None:
            dic.account_all_subprograms()
        self.rt = Runtime(self.rsp, dic)
        self.addr2line = {}
        self.ch_line2var = defaultdict(list)
        self.chc_line2var = defaultdict(list)

    def set_br_by_line(self, lineno, cb):
        line_map = self.rt.dic.find_line_map(bstr(basename(self.srcfile)))
        line_descs = line_map[lineno]

        if len(line_descs) < 1:
            raise RuntimeError(
                "No breakpoint addresses for line %s:%d (%s)" % (
                    self.srcfile, lineno, self.session_type
                )
            )

        # A line may be associated with several addresses. Setting breakpoints
        # on all of them may result in multiple stops on the line. It confuses
        # `DebugComparator`. However, some statements (like `return`) can
        # be duplicated in several addresses. So, breakpoints are set on all
        # addresses to catch the control flow everywhere.
        if self.verbose and 1 < len(line_descs):
            print("Breakpoint at %s:%d has many addresses in %s session."
                " The test may be incorrect." % (
                    self.srcfile, lineno, self.session_type
                )
            )

        for desc in line_descs:
            addr = self.rt.target.reg_fmt % desc.state.address
            self.addr2line[addr] = lineno
            self.rt.add_br(addr, cb)

    def _execute_debug_comment(self):
        lineno = 1

        with open(self.srcfile, 'r') as f:
            re_comment = compile("^.*//\$(.+)$")
            for line in f:
                mi = re_comment.match(line)
                if mi:
                    glob = DebugCommandExecutor(locals(), lineno)
                    exec(mi.group(1), glob)
                lineno += 1

    @property
    def _var_size(self):
        re_size = compile("^.+_(?:u?(\d+))_.+$")
        size_str = re_size.match(basename(self.srcfile)).group(1)
        return int(size_str) // 8

    def _dump_var(self, addr, lineno, var_names):
        dump = (self.session_type, self.srcfile, dict(
            elf = self.elffile,
            addr = addr,
            lineno = lineno,
            vars = dict(
                map(lambda x: (x, self.rt[x].fetch(self._var_size)),
                    var_names if var_names else self.rt
                )
            ),
            regs = self.rt.target.regs
        ))
        if self.rt.target.verbose:
            print(dump[2].values())
        self.queue.put(dump)

    def _dump(self, addr, lineno):
        dump = (self.session_type, self.srcfile, dict(
            elf = self.elffile,
            addr = addr,
            lineno = lineno,
            regs = self.rt.target.regs
        ))
        if self.rt.target.verbose:
            print(dump[2].values())
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

        for br in list(self.rt.target.br):
            self.rt.target.del_br(br)
        self.rt.target.exit = True
    # end debugging callbacks

    def kill(self):
        self.rt.target.send(b'k')

    def detach(self):
        self.rt.target.send(b'D')

    def port_close(self):
        self.rt.target.port.close()


class OracleSession(DebugSession):

    def __init__(self, *args):
        super(OracleSession, self).__init__(*args)
        self.session_type = "oracle"

    def main(self):
        self._execute_debug_comment()
        self.rt.target.run(setpc = False)


class TargetSession(DebugSession):

    def __init__(self, *args):
        super(TargetSession, self).__init__(*args)
        self.session_type = "target"

    def load(self):
        if self.rt.target.verbose:
            print("load %s" % self.elffile)

        loading = get_elffile_loading(self.elf)
        for data, addr in loading:
            self.rt.target.store(data, addr)

    def main(self):
        self._execute_debug_comment()
        if not c2t_cfg.rsp_target.user:
            self.load()
        # TODO: use future 'entry' feature
        new_pc = (
            self.rt.dic.symtab.get_symbol_by_name("main")[0].entry.st_value
        )
        if c2t_cfg.rsp_target.sp is not None:
            self.rt.target.set_reg(c2t_cfg.rsp_target.sp, new_pc + 0x10000)
        self.rt.target.set_reg(self.rt.target.pc_reg, new_pc)
        self.rt.target.run(setpc = False)


class ProcessWithErrCatching(Thread):

    def __init__(self, *popen_args, **popen_kw):
        Thread.__init__(self)

        if isinstance(popen_args[0], str):
            popen_kw.setdefault("shell", True)
        popen_kw["stdout"] = popen_kw["stderr"] = PIPE

        self.popen_args = popen_args
        self.popen_kw = popen_kw

        cmd = popen_args[0]
        self.prog = cmd.split(' ')[0] if isinstance(cmd, str) else cmd[0]

    def run(self):
        self._wiped = False

        self.process = process = Popen(*self.popen_args, **self.popen_kw)
        __, err = process.communicate()

        # If the process has been explicitly wiped, do not `c2t_exit`
        if not self._wiped:
            if process.returncode != 0:
                c2t_exit(err, prog = self.prog)

    def wipe(self):
        "Kills the process with its tree."
        self._wiped = True

        stack = [psutil_Process(self.process.pid)]

        while stack:
            process = stack.pop()

            try:
                stack.extend(process.children())
                process.kill()
            except NoSuchProcess:
                # killing process on a previous iteration may result in
                # self-termination of current process.
                pass

        self.join()


def oracle_tests_run(tests_queue, port_queue, res_queue, is_finish, verbose,
    timeout
):
    while True:
        try:
            test_src, test_elf = tests_queue.get(timeout = 0.1)
        except Empty:
            if is_finish.value:
                break
            continue

        gdbserver_port = port_queue.get(block = True)

        gdbserver = ProcessWithErrCatching(
            c2t_cfg.gdbserver.run.gen_popen_args(
                port = gdbserver_port,
                bin = test_elf,
                c2t_dir = C2T_DIR,
                test_dir = C2T_TEST_DIR
            )
        )
        gdbserver.start()

        if not wait_for_tcp_port(gdbserver_port):
            c2t_exit("gdbserver malfunction")

        session = OracleSession(archmap[ORACLE_CPU], test_src,
            str(gdbserver_port), test_elf, res_queue, verbose
        )

        if session.run(timeout):
            gdbserver.wipe()
        else:
            session.kill()
            gdbserver.join()
            session.port_close()

    res_queue.put(("oracle", None, "TEST_EXIT"))


def run_qemu(test_elf, qemu_port, qmp_port, verbose):
    if qmp_port:
        qmp_args = ("-qmp", "tcp:localhost:%d,server,nowait" % qmp_port)
    else:
        qmp_args = ()

    cmd = c2t_cfg.qemu.run.gen_popen_args(*qmp_args, **dict(
        port = qemu_port,
        bin = test_elf,
        c2t_dir = C2T_DIR,
        test_dir = C2T_TEST_DIR,
    ))

    if verbose:
        print(cmd)

    qemu = ProcessWithErrCatching(cmd)
    qemu.start()
    return qemu


def target_tests_run(tests_queue, port_queue, res_queue, is_finish, reuse,
    verbose, timeout
):
    qemu = None
    session = None
    qmp_port = None
    qmp = None
    while True:
        try:
            test_src, test_elf = tests_queue.get(timeout = 0.1)
        except Empty:
            if is_finish.value:
                if reuse and qemu and session:
                    session.kill()
                    qemu.join()
                    session.port_close()
                break
            continue
        else:
            if reuse and session and qmp:
                qmp("stop")
                qmp("system_reset")
                session.reset(test_src, test_elf)
            else:
                qemu_port = port_queue.get(block = True)
                if (not c2t_cfg.rsp_target.user
                    and (reuse or c2t_cfg.rsp_target.qemu_reset)
                ):
                    qmp_port = port_queue.get(block = True)

                qemu = run_qemu(test_elf, qemu_port, qmp_port, verbose)

                if not wait_for_tcp_port(qemu_port):
                    c2t_exit("qemu malfunction")

                if qmp_port and wait_for_tcp_port(qmp_port):
                    qmp = QMP(qmp_port)

                session = TargetSession(c2t_cfg.rsp_target.rsp, test_src,
                    str(qemu_port), test_elf, res_queue, verbose
                )

            if qmp and c2t_cfg.rsp_target.qemu_reset:
                # TODO: use future 'entry' feature
                session.rt.target[4] = pack("<I",
                    session.rt.dic.symtab.get_symbol_by_name(
                        "main"
                    )[0].entry.st_value
                )
                qmp("system_reset")

            if session.run(timeout):
                qemu.wipe()

                # Qemu has been terminated and cannot be reused
                session = None
                qmp = None
            else:
                if not reuse:
                    session.kill()
                    qemu.join()
                    session.port_close()

    res_queue.put(("target", None, "TEST_EXIT"))

class FreePortFinder(Process):

    def __init__(self, queue, count,  start = 4321):
        super(FreePortFinder, self).__init__()
        self.port_queue = queue
        self.count = count
        self.port_start = start

    def run(self):
        start = self.port_start
        for i in range(0, self.count):
            free = find_free_port(start)
            self.port_queue.put(free)
            # TODO: overflow 0x10000
            start = free + 1


class C2TTestBuilder(Process):
    """ A helper class that builds tests """

    def __init__(self, compiler, tests, tests_tail, tests_queue, is_finish,
        verbose
    ):
        super(C2TTestBuilder, self).__init__()
        self.compiler = compiler
        self.tests = tests
        self.tests_tail = tests_tail
        self.tests_queue = tests_queue
        self.is_finish = is_finish
        self.verbose = verbose

    def test_build(self, test_src, test_ir, test_bin):
        substitutions = dict(
            src = test_src,
            ir = test_ir,
            bin = test_bin,
            c2t_dir = C2T_DIR,
            test_dir = C2T_TEST_DIR,
        )
        for run in self.compiler:
            cmd = run.gen_popen_args(**substitutions)
            if self.verbose:
                print(cmd)
            cmpl_unit = ProcessWithErrCatching(cmd)
            cmpl_unit.start()
            cmpl_unit.join()

    def run(self):
        bin_dir = join(C2T_WORK_DIR, self.tests_tail, "bin")
        ir_dir = join(C2T_WORK_DIR, self.tests_tail, "ir")

        print("Binaries: " + bin_dir)
        print("Intermediates: " + ir_dir)

        # creates tests subdirectories if they don't exist
        for sub_dir in (bin_dir, ir_dir):
            makedirs(sub_dir, exist_ok = True)

        for test in self.tests:
            test_name = test[:-2]
            test_src = join(C2T_TEST_DIR, test)
            test_bin = join(bin_dir, test_name)

            if not exists(test_bin) or getmtime(test_bin) < getmtime(test_src):
                test_ir = join(ir_dir, test_name)

                self.test_build(test_src, test_ir, test_bin)

            self.tests_queue.put((test_src, test_bin))
        self.is_finish.value = 1


def start_cpu_testing(tests, jobs, reuse, verbose,
    no_run = False,
    errors2stop = 1,
    with_logs = False,
):
    oracle_tests_queue = Queue(0)
    target_tests_queue = Queue(0)
    is_finish_oracle = Value('i', 0)
    is_finish_target = Value('i', 0)

    oracle_tb = C2TTestBuilder(c2t_cfg.oracle_compiler, tests,
        ORACLE_CPU, oracle_tests_queue, is_finish_oracle, verbose
    )
    target_tb = C2TTestBuilder(c2t_cfg.target_compiler, tests,
        c2t_cfg.rsp_target.march, target_tests_queue, is_finish_target, verbose
    )

    oracle_tb.start()
    target_tb.start()

    if no_run:
        oracle_tb.join()
        target_tb.join()
        return

    port_queue = Queue(0)

    if not c2t_cfg.rsp_target.user:
        # Finding ports for Qemu, QMP server and gdbserver
        pf = FreePortFinder(port_queue, len(tests) * 3)
    else:
        # Finding ports for Qemu and gdbserver
        pf = FreePortFinder(port_queue, len(tests) * 2)

    pf.start()

    res_queue = Queue(0)

    if jobs > len(tests):
        jobs = len(tests)

    timeout = float(c2t_cfg.rsp_target.test_timeout)

    tests_run_processes = []
    for i in range(0, jobs):
        oracle_trp = Process(
            target = oracle_tests_run,
            args = [oracle_tests_queue, port_queue, res_queue,
                is_finish_oracle, verbose, timeout
            ]
        )
        target_trp = Process(
            target = target_tests_run,
            args = [target_tests_queue, port_queue, res_queue,
                is_finish_target, reuse, verbose, timeout
            ]
        )
        tests_run_processes.append((oracle_trp, target_trp))
        oracle_trp.start()
        target_trp.start()

    # Tests we are waiting for
    tests_left = set(tests)

    dc = DebugComparator(res_queue, jobs)
    for err in dc.start():
        test = relpath(err.test, C2T_TEST_DIR)
        tests_left.discard(test)

        print(err)

        if not tests_left:
            break
        if errors2stop:
            errors2stop -= 1
            if errors2stop == 0:
                killpg(0, SIGKILL)

    oracle_tb.join()
    target_tb.join()
    pf.join()
    for oracle_trp, target_trp in tests_run_processes:
        oracle_trp.join()
        target_trp.join()

    if with_logs:
        logs_dir = join(
            C2T_WORK_DIR,
            "logs",
            strftime(C2T_LOG_TIME_FMT, localtime()),
        )
        print("Logs: " + logs_dir)
        makedirs(logs_dir, exist_ok = True)

        for test, log in dc.test2logs.items():
            for runner in log.iter_runners():
                test_name = relpath(test, C2T_TEST_DIR)
                log_file_name = test_name + "." + runner + ".log"
                log_file_path = join(logs_dir, log_file_name)
                log.to_file(runner, log_file_path)


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

    # TODO: check for {bin} usage

    for compiler, compiler_name in (
        (c2t_cfg.target_compiler, "target_compiler"),
        (c2t_cfg.oracle_compiler, "oracle_compiler")
    ):
        for run in compiler:
            if run.has_substring("{bin}"):
                break
        else:
            c2t_exit("{bin} is not used", prog = "%s: %s" % (
                config, compiler_name
            ))


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
        formatter_class = HelpFormatter
    )
    arg = parser.add_argument
    arg("config",
        type = str,
        help = ("configuration file for {prog} (see sample and examples in "
            "{dir})".format(
                prog = parser.prog,
                dir = C2T_CONFIGS_DIR
            )
        )
    )
    DEFAULT_REGEXPS = testfilter([(testfilter.RE_INCLD, ".*\.c"),])
    arg("-t", "--include",
        type = str,
        metavar = "RE_INCLD",
        action = TestfilterCLI,
        dest = "regexps",
        default = DEFAULT_REGEXPS,
        help = ("regular expressions to include a test set "
            "(tests are located in %s)" % C2T_TEST_DIR
        )
    )
    arg("-s", "--exclude",
        type = str,
        metavar = "RE_EXCLD",
        action = TestfilterCLI,
        dest = "regexps",
        default = DEFAULT_REGEXPS,
        help = ("regular expressions to exclude a test set "
            "(tests are located in %s)" % C2T_TEST_DIR
        )
    )
    arg("-j", "--jobs",
        type = int,
        dest = "jobs",
        default = 1,
        help = "allow N debugging jobs at once"
    )
    arg("-r", "--reuse",
        action = "store_true",
        help = "reuse debug servers after each test (now only QEMU)"
    )
    arg("-v", "--verbose",
        action = "store_true",
        help = "increase output verbosity"
    )
    arg("-e", "--errors",
        type = int,
        default = 1,
        metavar = "N",
        help = "stop on N-th error, 0 - no stop mode"
    )
    arg("-l", "--with-logs",
        action = "store_true",
        help = "write *.oracle/target.log files near tests"
    )
    arg("-n", "--no-run",
        action = "store_true",
        help = "build binaries only"
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

    glob = dict(
        i for i in config_api.__dict__.items() if i[0] in config_api.__all__
    )

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
        else:
            c2t_exit("No `C2TConfig` instance was defined by the config "
                     "(see sample and examples in {dir})".format(
                    dir = C2T_CONFIGS_DIR
                ),
                prog = config
            )

    verify_config_components(config)

    incl, regexp, tests = args.regexps.find_files(C2T_TEST_DIR)
    if not tests:
        parser.error("no matches in {dir} with {var} {regexp}".format(
            dir = C2T_TEST_DIR,
            var = "inclusive" if incl else "exclusive",
            regexp = cli_repr(regexp)
        ))

    jobs = args.jobs
    if jobs < 1:
        parser.error("wrong number of jobs: %s" % jobs)

    start_cpu_testing(tests, jobs, args.reuse, args.verbose,
        no_run = args.no_run,
        with_logs = args.with_logs,
        errors2stop = args.errors
    )
    killpg(0, SIGTERM)


if __name__ == "__main__":
    main()
