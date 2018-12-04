#!/usr/bin/env python
"""QEMU CPU Testing Tool"""

from sys import (
    path,
    stderr
)
from os import (
    listdir,
    killpg
)
from os.path import (
    join,
    split,
    dirname,
    exists,
    basename
)
from inspect import (
    getmembers,
    getmro,
    isclass
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

# use custom pyrsp and pyelftools
path.insert(0, join(split(__file__)[0], "pyrsp"))
path.insert(0, join(split(__file__)[0], "debug", "pyelftools"))

from pyrsp.rsp import (
    RemoteTarget
)
from pyrsp import (
    targets
)
from pyrsp.utils import (
    pack
)
from elftools.elf.elffile import (
    ELFFile
)
from debug import (
    PreLoader
)
from c2t import (
    CommentParser
)

ARCHMAP = {
    name.lower(): obj for name, obj in getmembers(targets)
        if isclass(obj) and RemoteTarget in getmro(obj)[1:]
}

C2T_ERRMSG_FORMAT = "{prog}:\x1b[31m error:\x1b[0m {msg} {arg}\n"

C2T_DIR = dirname(__file__) or '.'
C2T_CONFIGS_DIR = join(C2T_DIR, "c2t", "configs")
C2T_TEST_DIR = join(C2T_DIR, "c2t", "tests")
C2T_TEST_IR_DIR = join(C2T_TEST_DIR, "ir")
C2T_TEST_BIN_DIR = join(C2T_TEST_DIR, "bin")


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


class DebugProcess(Process):
    """ Debug session process """

    def __init__(self, target, srcfile, port, elffile, queue, verbose,
                 oracle = False):
        Process.__init__(self)
        self.target = target(port, elffile,
            verbose = verbose,
            host = oracle
        )
        self.srcfile = srcfile
        self.elffile = elffile
        self.port = port
        self.queue = queue
        self.cb = {
            "br": self.__br,
            "bre": self.__bre,
            "brc": self.__brc,
            "ch": self.__ch
        }

    def __br(self, lineno, param = None):
        addr = self.target.get_hex_str(
            self.target.elf.src_map[lineno]["start"]
        )
        self.target.set_br(addr, self.continue_cb)

    def __brc(self, lineno, param = None):
        addr_s = self.target.get_hex_str(
            self.target.elf.src_map[lineno]["start"]
        )
        addr_e = self.target.elf.src_map[lineno]["end"]

        if addr_e:
            addr_e = self.target.get_hex_str(addr_e)

            self.target.set_br(addr_s, self.cycle_cb,
                lineno = lineno,
                old = addr_e
            ) # check in start
            self.target.set_br(addr_e, self.cycle_cb,
                lineno = lineno,
                old = addr_s
            ) # check in end
        else :
            self.target.set_br(addr_s, self.continue_cb, lineno = lineno)

    def __bre(self, lineno, param = None):
        addr = self.target.get_hex_str(
            self.target.elf.src_map[lineno]["start"]
        )
        self.target.set_br(addr, self.finish_cb)

    def __ch(self, lineno, param = None):
        addr = self.target.elf.src_map[lineno]["end"]

        if addr:
            addr = self.target.get_hex_str(
                self.target.elf.src_map[lineno]["end"]
            )
        else:
            addr = self.target.get_hex_str(
                self.target.elf.src_map[lineno]["start"]
            )

        self.target.set_br(addr, self.dump_cb,
            lineno = lineno,
            name = param
        ) # check in start

    def __set_breakpoints(self):
        lineno = 0

        with open(self.srcfile, 'r') as f:
            for line in f:
                lineno = lineno + 1
                pos = line.find("//$")
                if pos != -1:
                    command = line[pos:]
                    command = command[command.find('$') + 1:]
                    exec(command, {}, CommentParser(locals(), lineno))
        self.target.on_finish.append(self.finish_cb)

    def load(self, verify):
        """ loads binary belonging to elf to beginning of .text
segment (alias self.elf.workarea), and if verify is set read
it back and check if it matches with the uploaded binary.
        """
        if self.target.verbose:
            print("load %s" % self.target.elf.name)

        with open(self.elffile, "rb") as stream:
            sections_names = [".text", ".rodata", ".data", ".bss"]
            preloader = PreLoader(sections_names, ELFFile(stream))
            sections_data = preloader.get_sections_data()
            addr = self.target.elf.workarea
            for name in sections_names:
                if sections_data[name].data is not None:
                    self.target.store(sections_data[name].data, addr)
                    addr = addr + sections_data[name].data_size

            buf = sections_data[".text"].data
            if verify:
                if self.target.verbose:
                    print("verify test")
                if not self.target.dump(len(buf)) == buf:
                    raise ValueError("uploaded binary failed to verify")
                if self.target.verbose:
                    print("OK")

    def run_session(self):
        """ Runs the target handling breakpoints.
For non-oracle target it also sets program counter to either the start
symbol (if configured) or entry point by the ELF file header (if not).
        """
        if not self.target.rsp.host:
            if self.start:
                entry = self.target.get_hex_str(
                    self.target.elf.symbols[self.target.start]
                )
            else:
                entry = self.target.get_hex_str(self.target.elf.entry)

            if self.target.verbose:
                print("set new pc: @test (0x%s) OK" % entry)
            self.target.set_reg(self.target.pc, entry)
            if self.target.verbose:
                print("continuing")

        sig = self.target.rsp.run()
        while sig[:3] in ["T05", "S05"]:
            self.target.handle_br()
            sig = self.target.rsp.run()

        self.finish_cb()

    def run(self):
        self.__set_breakpoints()
        self.target.start = "main"
        self.target.refresh_regs()
        if not self.target.rsp.host:
            self.load(True)
            self.target.set_sp()
        self.run_session()

    def stop(self):
        """Stopping the process
        """
        self.target.rsp.port.write(pack('k'))
        self.target.rsp.port.close()
        self.terminate()

    def dump_cb(self):
        """ rsp_dump callback, hit if rsp_dump is called. Outputs to
stdout the source line, and a hexdump of the memory pointed by $r0
with a size of $r1 bytes. Then it resumes running.
        """
        self.target.dump_regs()

        vals = self.target.dump_vars("ch")
        addr = self.target.regs[self.target.pc]

        dump = {
            addr: {
                "variables": vals,
                "lineno"   : self.target.br[addr]["lineno"],
                "regs"     : self.target.dump_regs()
            }
        }
        if self.target.verbose:
            print(dump.values())
        self.queue.put(dump.copy())
        dump.clear()
        self.target.del_br(addr, quiet = True)

    def continue_cb(self):
        self.target.dump_regs()

        self.target.del_br(self.target.regs[self.target.pc], quiet = True)

    def cycle_cb(self):
        self.target.dump_regs()

        addr = self.target.regs[self.target.pc]

        if addr < self.target.br[addr]["old"] and self.target.br[addr]["old"]:
            vals = self.target.dump_vars("brc")
            dump = {
                addr: {
                    "variables" : vals,
                    "lineno"    : self.target.br[addr]["lineno"],
                    "regs"      : self.target.dump_regs()
                }
            }
            if self.target.verbose:
                print(dump.values())
            self.queue.put(dump.copy())
            dump.clear()

        if (    self.target.br[addr]["old"]
            and self.target.br[addr]["old"] not in self.target.br
        ):
            self.target.set_br(self.target.br[addr]["old"],
                self.target.br[addr]["cb"],
                lineno = self.target.br[addr]["lineno"],
                old = addr
            )

        self.target.del_br(addr, quiet = True)

    def finish_cb(self):
        """ final breakpoint, if hit it deletes all breakpoints,
continues running the cpu, and detaches from the debugging device
        """
        self.target.dump_regs()

        for br in self.target.br.keys()[:]:
            self.target.del_br(br)

        if self.target.verbose:
            print("\ncontinuing and detaching")

        if self.queue:
            self.queue.put("CMP_EXIT")
        self.target.rsp.finish()
        exit(0)


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

        for run_script in self.cmpl_unit.get_run():
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
        if self.config.march in ARCHMAP:
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
        pass


class C2TArgumentParser(ArgumentParser):
    """ Custom ArgumentParser """

    def __init__(self):
        ArgumentParser.__init__(self,
            description = "CPU Testing Tool",
            epilog = ("supported targets: {targets}".format(
                targets = ', '.join("%s" % arch for arch in ARCHMAP)
            ))
        )

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
    parser = C2TArgumentParser()
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
