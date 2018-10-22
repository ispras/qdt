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
        return self.target.get_val(addr, size)
