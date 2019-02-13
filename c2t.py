#!/usr/bin/env python
"""QEMU CPU Testing Tool"""

from sys import (
    stderr
)
from os import (
    listdir,
    killpg,
    makedirs,
    setpgrp
)
from os.path import (
    join,
    dirname,
    exists,
    basename
)
# from inspect import (
#     getmembers,
#     getmro,
#     isclass
# )
from errno import (
    EEXIST
)
from argparse import (
    ArgumentParser
)
from re import (
    compile,
    findall
)
from multiprocessing import (
    Process,
    Queue
)
from subprocess import (
    Popen,
    PIPE
)
from signal import (
    SIGKILL
)
from platform import (
    machine
)
from common import (
    pypath,
    lazy
)
from debug import (
    InMemoryELFFile,
    DWARFInfoCache,
    PreLoader,
    Runtime
)
with pypath("pyrsp"):
    from pyrsp.rsp import (
        archmap
    )
    from pyrsp.utils import (
        pack,
        wait_for_tcp_port,
        QMP
    )
from c2t import (
    CommentParser,
    DebugComparison
)

# ARCHMAP = {
#     name.lower(): obj for name, obj in getmembers(targets)
#         if isclass(obj) and RemoteTarget in getmro(obj)[1:]
# }

C2T_ERRMSG_FORMAT = "{prog}:\x1b[31m error:\x1b[0m {msg} {arg}\n"

C2T_DIR = dirname(__file__) or '.'
C2T_CONFIGS_DIR = join(C2T_DIR, "c2t", "configs")
C2T_TEST_DIR = join(C2T_DIR, "c2t", "tests")
C2T_TEST_IR_DIR = join(C2T_TEST_DIR, "ir")
C2T_TEST_BIN_DIR = join(C2T_TEST_DIR, "bin")

try:
    makedirs(C2T_TEST_IR_DIR)
    makedirs(C2T_TEST_BIN_DIR)
except OSError as e:
    if e.errno != EEXIST:
        # TODO: raise exception or error message?
        raise


# TODO: improve this
def errmsg(msg,
    prog = __file__,
    arg = '',
    with_exit = True
):
    print(C2T_ERRMSG_FORMAT.format(
        prog = basename(prog),
        msg = msg,
        arg = arg
    ))
    if with_exit:
        exit(1)


# TODO: add good name
class C2tRuntime(Process):
    # TODO: add good comment
    """ Debug session unit """

    def __init__(self, target, srcfile, port, elffile, queue, verbose):
        self.elf = InMemoryELFFile(elffile)
        di = self.elf.get_dwarf_info()
        dic = DWARFInfoCache(di,
            symtab = self.elf.get_section_by_name(b".symtab")
        )
        # TODO: rename this
        target = target(port, elffile,
            verbose = verbose
        )
        self.rt = Runtime(target, dic)
        super(C2tRuntime, self).__init__()
        self.srcfile = srcfile
        self.port = port
        self.queue = queue
        self.addr2line = {}
        self.line2var = {}

    def __call__(self, command, lineno, var_name = None):
        if command is "br":
            self._set_br_by_line(lineno, self.continue_cb)
        elif command is "bre":
            self._set_br_by_line(lineno, self.finish_cb)
        elif command is "brc":
            self._set_br_by_line(lineno, self.cycle_cb)
        elif command is "chc":
            self._set_br_by_line(lineno, self.cycle_dump_cb, var_name)
        elif command is "ch":
            self._set_br_by_line(lineno, self.dump_cb, var_name)
        else:
            raise RuntimeError

    def _set_br_by_line(self, lineno, cb, var_name = None):
        line_map = self.rt.dic.find_line_map(self.srcfile)
        line_descs = line_map[lineno]
        if var_name is not None:
            self.line2var[lineno] = var_name
        for desc in line_descs:
            addr = self.rt.target.reg_fmt % desc.state.address
            self.addr2line[addr] = lineno
            self.rt.target.set_br_a(addr, cb)

    def _set_breakpoints(self):
        lineno = 1

        with open(self.srcfile, 'r') as f:
            re_command = compile("^.*//\$(.*)$")
            for line in f:
                mi = re_command.match(line)
                if mi:
                    command = mi.group(1)
                    exec(command, {}, CommentParser(locals(), lineno))
                lineno += 1

    @lazy
    def _var_size(self):
        re_size = compile("^.+_(?:u?(\d+))_.+$")
        size_str = re_size.match(basename(self.srcfile)).group(1)
        return int(size_str) / 8

    def dump(self):
        """ rsp_dump callback, hit if rsp_dump is called. Outputs to
stdout the source line, and a hexdump of the memory pointed by $r0
with a size of $r1 bytes. Then it resumes running.
        """

        addr = self.rt.target.regs[self.rt.target.pc_reg]
        lineno = self.addr2line[addr]

        var_name = self.line2var.get(lineno)
        var_names, var_vals = (
            ([var_name], [self.rt[var_name].fetch(self._var_size)])
            if var_name is not None else
            ([name for name in self.rt],
            [self.rt[name].fetch(self._var_size) for name in self.rt])
        )

        dump = {
            addr: {
                "vars": {
                    name: val for name, val in zip(var_names, var_vals)
                },
                "lineno": lineno,
                "regs": self.rt.target.regs
            }
        }
        if self.rt.target.verbose:
            print(dump.values())
        self.queue.put(dump.copy())
        dump.clear()
        return addr

    def dump_cb(self):
        addr = self.dump()
        self.rt.target.del_br(addr, quiet = True)

    def cycle_dump_cb(self):
        self.dump()
        self.rt.target.step_over_br()

    def continue_cb(self):
        self.rt.target.del_br(self.rt.target.regs[self.rt.target.pc_reg],
            quiet = True
        )

    def cycle_cb(self):
        self.rt.target.step_over_br()

    def finish_cb(self):
        """ final breakpoint, if hit it deletes all breakpoints,
continues running the cpu, and detaches from the debugging device
        """
        if self.queue:
            self.queue.put("CMP_EXIT")
        self.rt.target.finish_cb()
        self.rt.target.port.close()


class C2tOracle(C2tRuntime):

    def run(self):
        self._set_breakpoints()
        self.rt.target.start = "main"
        self.rt.target.refresh_regs()
        self.rt.target.run(setpc = False)


class C2tTarget(C2tRuntime):

    def load(self, verify):
        """ loads binary belonging to elf to beginning of .text
segment (alias self.elf.workarea), and if verify is set read
it back and check if it matches with the uploaded binary.
        """
        if self.rt.target.verbose:
            print("load %s" % self.rt.target.elf.name)

        sections_names = [".text", ".rodata", ".data", ".bss"]
        preloader = PreLoader(sections_names, self.elf)
        sections_data = preloader.get_sections_data()
        addr = self.rt.target.elf.workarea
        for name in sections_names:
            if sections_data[name].data is not None:
                self.rt.target.store(sections_data[name].data, addr)
                addr = addr + sections_data[name].data_size

        buf = sections_data[".text"].data
        if verify:
            if self.rt.target.verbose:
                print("verify test")
            if not self.rt.target.dump(len(buf)) == buf:
                raise ValueError("uploaded binary failed to verify")
            if self.rt.target.verbose:
                print("OK")

    def run(self):
        self._set_breakpoints()
        self.rt.target.start = "main"
        self.rt.target.refresh_regs()
        self.load(True)
        addr = "%0*x" % (self.rt.target.arch['bitsize'] >> 2, 65536)
        # TODO: don't hardcode this
        self.rt.target.set_reg('sp', addr)
        self.rt.target.run(start = "main", setpc = True)


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
        output, error = process.communicate()
        if process.returncode != 0:
            errmsg(error,
                prog = self.prog,
                with_exit = False
            )
            killpg(0, SIGKILL)


class TestBuilder(Process):
    """ A helper class that builds tests """

    def __init__(self, march, cmpl_unit, tests, elf_queue):
        Process.__init__(self)
        self.suffix = "_%s" % march
        self.cmpl_unit = cmpl_unit
        self.tests = tests
        self.elf_queue = elf_queue

    def test_build(self, test):
        test_name = test[:-2]
        test_src = join(C2T_TEST_DIR, test)
        test_ir = join(C2T_TEST_IR_DIR, test_name)
        test_bin = join(C2T_TEST_BIN_DIR, test_name + self.suffix)
        run_script = ''

        for run_script in self.cmpl_unit.run_script:
            cmpl_unit = ProcessWithErrCatching(run_script.format(
                src = test_src,
                ir = test_ir,
                bin = test_bin
            ))
            cmpl_unit.start()
            cmpl_unit.join()

        ext = findall("-o {bin}(\S*)", run_script).pop()
        self.elf_queue.put((test_src, test_bin + ext))

    def run(self):
        for test in self.tests:
            # Builds another test if 'elf_queue' contains one element
            while self.elf_queue.qsize() > 1:
                pass
            self.test_build(test)


class CpuTestingTool(object):

    def __init__(self, config, tests, verbose):
        self.config = self.get_cfg(config)
        self.verify_config(config)
        self.oracle_cpu = "amd64" if machine() == "x86_64" else "i386"
        self.target_elf_queue = Queue(0)
        self.oracle_elf_queue = Queue(0)
        self.target_builder = TestBuilder(self.machine_type,
            self.config.target_compiler, tests, self.target_elf_queue
        )
        self.oracle_builder = TestBuilder(self.oracle_cpu,
            self.config.oracle_compiler, tests, self.oracle_elf_queue
        )
        self.verbose = verbose

    @staticmethod
    def get_cfg(config):
        try:
            exec(open(config).read())
            return c2t_cfg
        except Exception as e:
            errmsg(e, prog = config)

    def verify_config(self, config):
        if self.config.march in archmap:
            self.machine_type = self.config.march
        else:
            errmsg("unsupported target:", arg = self.config.march)

        errmsg1 = "compiler specified with frontend or backend"
        errmsg2 = "frontend or backend are not specified"
        if self.config.target_compiler.compiler is not None:
            if (    self.config.target_compiler.frontend is not None
                or  self.config.target_compiler.backend is not None
            ):
                errmsg(errmsg1, prog = "%s: target_compiler" % config)
        elif (    self.config.target_compiler.frontend is None
              or  self.config.target_compiler.backend is None
        ):
            errmsg(errmsg2, prog = "%s: target_compiler" % config)

        if self.config.oracle_compiler.compiler is not None:
            if (    self.config.oracle_compiler.frontend is not None
                or  self.config.oracle_compiler.backend is not None
            ):
                errmsg(errmsg1, prog = "%s: oracle_compiler" % config)
        elif (    self.config.oracle_compiler.frontend is None
              or  self.config.oracle_compiler.backend is None
        ):
            errmsg(errmsg2, prog = "%s: oracle_compiler" % config)

    def start(self):
        setpgrp()

        self.target_builder.start()
        self.oracle_builder.start()

        test_src, target_elf = self.target_elf_queue.get(block = True)

        qemu = ProcessWithErrCatching(
            self.config.qemu.run_script.format(bin = target_elf)
        )

        qemu.daemon = True

        oracle_queue = Queue(0)
        target_queue = Queue(0)

        qemu.start()

        # TODO: select port automatically or manually (from config) and
        # use find_free_port()
        if not wait_for_tcp_port(1234) or not wait_for_tcp_port(5678):
            killpg(0, SIGKILL)

        qmp = QMP(5678)

        while 1:
            test_src, oracle_elf = self.oracle_elf_queue.get(block = True)

            gdbserver = ProcessWithErrCatching(
                self.config.gdbserver.run_script.format(bin = oracle_elf)
            )

            gdbserver.daemon = True
            gdbserver.start()

            if not wait_for_tcp_port(4321):
                killpg(0, SIGKILL)

            oracle_session = C2tOracle(archmap[self.oracle_cpu], test_src,
                "4321", oracle_elf, oracle_queue, self.verbose
            )
            target_session = C2tTarget(archmap[self.machine_type], test_src,
                "1234", target_elf, target_queue, self.verbose
            )
            debug_comparison = DebugComparison(oracle_queue, target_queue)

            oracle_session.start()
            target_session.start()
            try:
                debug_comparison.start()
            except RuntimeError:
                killpg(0, SIGKILL)

            if self.target_elf_queue.empty() and self.oracle_elf_queue.empty():
                break

            oracle_session.join()
            target_session.join()

            qmp("system_reset")
            # TODO: wtf?
            gdbserver.terminate()

            test_src, target_elf = self.target_elf_queue.get(block = True)

        killpg(0, SIGKILL)


class C2TArgumentParser(ArgumentParser):
    """ ArgumentParser with custom error method """

    def error(self, msg, optval = ''):
        self.print_usage(stderr)
        self.exit(2, C2T_ERRMSG_FORMAT.format(
            prog = self.prog,
            msg = msg,
            arg = optval
        ))


def get_tests(regexp):
    r = compile("%s[.]c$" % regexp)
    return list(filter(r.match, listdir(C2T_TEST_DIR)))


def main():
    parser = C2TArgumentParser(
        description = "CPU Testing Tool",
        epilog = ("supported targets: {targets}".format(
            targets = ', '.join("%s" % arch for arch in archmap)
        ))
    )
    parser.add_argument("-c", "--config",
        type = str,
        dest = "config",
        help = "configuration file for %s" % parser.prog
    )
    parser.add_argument("-t", "--test",
        type = str,
        dest="regexp",
        help = ("regular expression that defines a test set"
             " (tests are located in %s)"
        ) % C2T_TEST_DIR
    )
    parser.add_argument("-v", "--verbose",
        action = "store_true",
        help = "increase output verbosity"
    )

    args = parser.parse_args()

    if not args.config or not args.regexp:
        parser.error("requires more input arguments to run")

    config = join(C2T_CONFIGS_DIR, "%s.py" % args.config)
    if not exists(config):
        config = join(C2T_DIR, "%s.py" % args.config)
        if not exists(config):
            parser.error("configuration file doesn't exist:",
                optval = args.config
            )

    tests = get_tests(args.regexp)
    if not tests:
        parser.error("no matches in %s with:" % C2T_TEST_DIR,
            optval = args.regexp
        )

    tf = CpuTestingTool(config, tests, args.verbose)
    tf.start()


if __name__ == "__main__":
    main()
