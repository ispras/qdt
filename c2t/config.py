__all__ = [
    "C2TConfig"
  , "edef"
  , "evar"
  , "Run"
  , "get_new_rsp"
  , "DebugClient"
  , "DebugServer"
  , "TestBuilder"
]

from collections import (
    namedtuple
)
from common import (
    pypath
)
with pypath("..pyrsp"):
    from pyrsp.rsp import (
        RSP,
        archmap
    )

from os import (
    environ,
)


def evar(name, default = None, hint = None):
    """Tries to get environment variable `name` value.
May print `hint` and/or provide `default` value if it's not set.
`default` can be a value factory (callable).
    """
    try:
        val = environ[name]
    except:
        print("%s: environment variable is not defined" % name)
        if hint is not None:
            print(hint)
        if default is None:
            raise
        else:
            if issubclass(type(default), type(evar)):
                # is callable
                val = default()
            else:
                val = default
            print("%s = %r (default)" % (name, val))
    return val


def edef(factory):
    "To be used as @decorator for default environment variable value factory."
    return evar(factory.__name__,
        default = factory,
        hint = factory.__doc__,
    )


# CPU Testing Tool configuration components
C2TConfig = namedtuple(
    "C2TConfig",
    "rsp_target qemu gdbserver target_compiler oracle_compiler"
)
class Run(namedtuple(
    "Run",
    "executable args"
)):

    def format_args(self, **format_input):
        args = self.args
        if isinstance(args, str):
            return args.format_map(format_input)
        else:
            return type(args)(arg.format_map(format_input) for arg in args)

    def gen_popen_args(self, *extra_args, **format_input):
        args = self.format_args(**format_input)
        if isinstance(args, str):
            return (
                self.executable
              + " "
              + args
              + " "
              + " ".join(extra_args)
            )
        else:
            return type(args)(
                (self.executable,)
              + tuple(args)
              + extra_args
            )

    def has_substring(self, ss):
        args = self.args
        if isinstance(args, str):
            return ss in args
        else:
            for arg in args:
                if ss in arg:
                    return True
            return False


def get_new_rsp(regs, pc, regsize, little_endian = True):
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


class DebugClient(object):

    def __init__(self, march, new_rsp = None, user = False, sp = None,
        qemu_reset = False, test_timeout = 10.0
    ):
        self.march = march
        if march in archmap:
            self.rsp = archmap[march]
        elif new_rsp is not None:
            self.rsp = new_rsp
        else:
            self.rsp = None
        self.user = user
        self.sp = sp
        self.qemu_reset = qemu_reset
        self.test_timeout = test_timeout


class DebugServer(object):

    def __init__(self, run):
        self.run = run


class TestBuilder(tuple):

    def __new__(cls, *runs):
        return tuple.__new__(cls, runs)

    # TODO: how to operate without runs?
    @property
    def run_script(self):
        for run in self:
            yield ' '.join(run)
