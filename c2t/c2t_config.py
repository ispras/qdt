__all__ = [
    "C2TConfig"
  , "Run"
  , "DebugUnit"
  , "CompileUnit"
]

from abc import (
    ABCMeta,
    abstractmethod
)
from collections import (
    namedtuple
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
    def get_run(self):
        """
    :returns:
        cmdline 'run' for unit

        """
        pass


class DebugUnit(C2TUnit):

    def __init__(self, run):
        self.run = run

    def get_run(self):
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
    def get_run(self):
        for run in self.runs:
            yield self.assemble_run(run)
