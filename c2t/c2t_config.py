__all__ = [
    "C2TConfig"
  , "Run"
  , "DebugUnit"
  , "CompileUnit"
  , "rsp_target"
]

from abc import (
    ABCMeta,
    abstractmethod
)
from collections import (
    namedtuple
)
from common import (
    pypath
)
with pypath("..pyrsp"):
    from pyrsp.rsp import (
        RSP
    )


# CPU Testing Tool configuration components
C2TConfig = namedtuple(
    "C2TConfig",
    "march qemu gdbserver target_compiler oracle_compiler"
)

# Cmdline 'run' components
Run = namedtuple(
    "Run",
    "executable args"
)


class C2TUnit(object):
    # TODO: concretize this comment
    """ This class defines common interface for 'CPU Testing Tool Unit'. """

    __metaclass__ = ABCMeta

    @staticmethod
    def assemble_run(run):
        return ' '.join([run.executable, run.args])

    @abstractmethod
    def run_script(self):
        """
    :returns:
        cmdline 'run' for unit

        """
        pass


class DebugUnit(C2TUnit):

    def __init__(self, run, gdb_target = None):
        self.run = run
        self.gdb_target = gdb_target

    @property
    def run_script(self):
        return self.assemble_run(self.run)


class CompileUnit(C2TUnit):

    def __init__(self,
                 compiler = None,
                 frontend = None,
                 backend = None,
                 linker = None
    ):
        self.compiler = compiler
        self.frontend = frontend
        self.backend = backend
        self.linker = linker
        self.runs = (
            filter(
                lambda v: v is not None,
                list([self.compiler, self.frontend, self.backend, self.linker])
            )
        )

    # TODO: how process when runs = []
    @property
    def run_script(self):
        for run in self.runs:
            yield self.assemble_run(run)


def rsp_target(regs, pc, regsize, little_endian = True):
    """Helper defining custom description of remote target CPU architecture
    for RSP.
    """

    class CustomRSP(RSP):
        def __init__(self, *a, **kw):
            self.arch = dict(
                regs = regs,
                endian = little_endian,
                bitsize = regsize
            )
            self.pc_reg = pc
            super(CustomRSP, self).__init__(*a, **kw)

    return CustomRSP
