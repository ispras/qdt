__all__ = [
    "Runtime"
]

from collections import (
    deque
)
from itertools import (
    repeat
)
from common import (
    cached,
    reset_cache
)
from .value import (
    Returned,
    Value
)

class Runtime(object):
    "A context of debug session with access to DWARF debug information."

    def __init__(self, target, dic):
        """
    :type target:
        pyrsp.rsp.RemoteTarget
    :param target:
        debug session descriptor

    :type dic:
        DWARFInfoCache
    :param dic:
        a global context

        """
        self.target = target
        self.dic = dic

        self.pc = target.pc_idx

        # cache of register values converted to integer
        self.regs = [None] * len(target.registers)

        # support for `cached` decorator
        self.__lazy__ = []

        self.object_stack = deque()

        # XXX: currently a host is always AMD64
        # TODO: account targets's calling convention
        return_reg_name = "rax"
        self.return_reg = target.registers.index(return_reg_name)

        # TODO: this must be done using DWARF because tetradsize and address
        # size are not same values semantically (but same by implementation).
        self.address_size = target.arch["tetradsize"] >> 1

        # Version number of debug session. It is incremented on each target
        # resumption. It helps detect using of not actual data. E.g. a local
        # variable of a function which is already returned.
        self.version = 0

        # When target resumes all cached data must be reset because it is not
        # actual now.
        target.on_resume.append(self.on_resume)

    def on_resume(self, *_, **__):
        self.version += 1

        self.regs[:] = repeat(None, len(self.regs))

        reset_cache(self)

    def get_reg(self, idx):
        regs = self.regs
        val = regs[idx]

        if val is None:
            tgt = self.target
            val_hex = tgt.get_thread_reg(idx)
            val = int(val_hex, 16)
            regs[idx] = val

        return val

    @cached
    def returned_value(self):
        """ Value being returned by current subprogram. Note that it is
normally correct only when the target is stopped at the subprogram epilogue.
        """
        pc = self.get_reg(self.pc)
        val_desc = Returned(self.dic, self.return_reg, pc)
        return Value(val_desc, runtime = self, version = self.version)

    @cached
    def subprogram(self):
        "Subprogram corresponding to current program counter."
        pc = self.get_reg(self.pc)
        return self.dic.subprogram(pc)

    @cached
    def frame(self):
        frame_expr = self.subprogram.frame_base

        frame = frame_expr.eval(self)
        return frame

    @cached
    def cfa(self):
        pc = self.get_reg(self.pc)
        cfa_expr = self.dic.cfa(pc)
        cfa = cfa_expr.eval(self)
        return cfa

    def push(self, object_value):
        self.object_stack.append(object_value)

    def pop(self):
        self.object_stack.pop()

    @property
    def object(self):
        stack = self.object_stack
        obj = stack.pop()
        loc = obj.eval(self)
        stack.append(obj)
        return loc

    def get_val(self, addr, size):
        target = self.target

        data = target.dump(size, addr)

        if target.arch["endian"]:
            data = reversed(data)

        # there the data is big-endian
        di = iter(data)
        val = ord(next(di))
        for d in di:
            val <<= 8
            val += ord(d)

        return val

    def __getitem__(self, name):
        """ Accessing variables by name.

Search order:
- current subprogram local data (variables, arguments, ...)
- global variables for compile unit of current subprogram
TODO: public global variables across all CUs
TODO: current CU's subprograms
TODO: public global subprograms
TODO: target registers

    :param name:
        of a variable

    :returns:
        corresponding runtime descriptor `Value`

        """

        prog = self.subprogram
        _locals = prog.data

        try:
            datum = _locals[name]
        except KeyError:
            cu = prog.die.cu
            _globals = self.dic.get_CU_global_variables(cu)
            try:
                datum = _globals[name]
            except KeyError:
                raise KeyError("No name '%s' found in runtime" % name)

        return Value(datum, runtime = self, version = self.version)
