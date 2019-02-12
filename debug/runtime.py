__all__ = [
    "Runtime"
]

from traceback import (
    print_exc
)
from threading import (
    Thread
)
from collections import (
    defaultdict,
    deque
)
from itertools import (
    repeat
)
from common import (
    charcodes,
    bstr,
    notifier,
    cached,
    reset_cache
)
from .value import (
    Returned,
    Value
)


@notifier("break")
class Breakpoints(object):

    def __init__(self, runtime):
        self._rt = runtime
        self._alive = True

    def __call__(self):
        rt = self._rt
        target = rt.target
        event = target.stop_event
        thread = target.thread

        rt._Runtime__notify_stop(*event)

        self.__notify_break()

        rt.on_resume(thread)
        # This breakpoint can be removed during preceding notification.
        if self._alive:
            target.step_over_br()

    # See: https://stackoverflow.com/a/5288992/7623015
    def __bool__(self): # Py3
        return bool(self.__break)

    __nonzero__ = __bool__ # Py2


@notifier(
    "stop", # RSP stop event parts: kind, `int` signal, `dict` data
    "resume" # thread id
)
class Runtime(object):
    "A context of debug session with access to DWARF debug information."

    def __init__(self, target, dic, return_reg_name = None):
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

        self.pc = target.registers.index(target.pc_reg)

        # cache of register values converted to integer
        self.regs = [None] * len(target.registers)

        # support for `cached` decorator
        self.__lazy__ = []

        self.object_stack = deque()

        if return_reg_name is None:
            # TODO: account targets's calling convention
            self.return_reg = 0
        else:
            self.return_reg = target.registers.index(return_reg_name)

        # TODO: this must be done using DWARF because "bitsize" and address
        # size are not same values semantically (but same by implementation).
        self.address_size = target.arch["bitsize"] >> 3

        # Version number of debug session. It is incremented on each target
        # resumption. It helps detect using of not actual data. E.g. a local
        # variable of a function which is already returned.
        self.version = 0

        # breakpoints and its handlers
        self.brs = defaultdict(lambda : Breakpoints(self))

    def add_br(self, addr_str, cb, quiet = False):
        cbs = self.brs[addr_str]
        if not cbs:
            self.target.set_br_a(addr_str, cbs, quiet)
        cbs.watch_break(cb)

    def remove_br(self, addr_str, cb, quiet = False):
        cbs = self.brs[addr_str]
        cbs.unwatch_break(cb)
        if not cbs:
            cbs._alive = False
            self.target.del_br(addr_str, quiet)

    def on_resume(self, thread, *_, **__):
        """ When target resumes all cached data must be reset because it is
not actual now.
        """

        self.version += 1

        self.regs[:] = repeat(None, len(self.regs))

        reset_cache(self)

        self.__notify_resume(thread)

    def get_reg(self, idx):
        regs = self.regs
        val = regs[idx]

        if val is None:
            tgt = self.target
            val_hex = tgt.regs[tgt.registers[idx]]
            val = int(val_hex, 16)
            regs[idx] = val

        return val

    def co_run_target(self):
        target = self.target

        def run():
            try:
                target.run(setpc = False)
            except:
                print_exc()
                print("Target PC 0x%x" % (self.get_reg(self.pc)))

            try:
                target.send(b"k")
            except:
                print_exc()

        t = Thread(target = run)
        t.name = "RSP client"
        t.start()

        while t.isAlive():
            yield False

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
        di = charcodes(data)
        val = next(di)
        for d in di:
            val <<= 8
            val += d

        return val

    def __iter__(self):
        prog = self.subprogram
        _locals = prog.data

        if _locals is not None:
            for _local in _locals:
                yield _local
        else:
            cu = prog.die.cu
            _globals = self.dic.get_CU_global_variables(cu)
            for _global in _globals:
                yield _global

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
        bname = bstr(name)

        try:
            datum = _locals[bname]
        except KeyError:
            cu = prog.die.cu
            _globals = self.dic.get_CU_global_variables(cu)
            try:
                datum = _globals[bname]
            except KeyError:
                raise KeyError("No name '%s' found in runtime" % name)

        return Value(datum, runtime = self, version = self.version)
