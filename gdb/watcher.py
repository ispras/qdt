__all__ = [
    "Watcher",
    "re_breakpoint_pos"
]

from inspect import (
    getmembers,
    ismethod
)
from re import (
    compile
)
from common import (
    notifier
)

re_breakpoint_pos = compile("^[^:]*:[1-9][0-9]*$")


def is_breakpoint_cb(object):
    if not ismethod(object):
        return False
    if not object.__name__.startswith("on_"):
        return False
    doc = object.__doc__
    return doc and re_breakpoint_pos.match(doc.splitlines()[0])


@notifier("runtime_set")
class Watcher(object):

    def __init__(self, dia, verbose = True):
        self.dia = dia
        self.verbose = verbose

        # inspect methods getting those who is a breakpoint handler
        self.breakpoints = brs = []
        for name, cb in getmembers(type(self), predicate = is_breakpoint_cb):
            file_name, line_str = cb.__doc__.splitlines()[0].split(":")
            line_map = dia.find_line_map(file_name)
            line_descs = line_map[int(line_str)]
            addr = line_descs[0].state.address
            brs.append((addr, getattr(self, name)))

    def init_runtime(self, rt):
        v = self.verbose
        quiet = not v

        self.rt = rt
        target = rt.target

        for addr, cb in self.breakpoints:
            addr_str = target.get_hex_str(addr)

            if v:
                print("br 0x" + addr_str + ", handler = " + cb.__name__)

            target.set_br(addr_str, cb, quiet = quiet)

        self.__notify_runtime_set(rt)

    def remove_breakpoints(self):
        "Removes breakpoints assigned by `init_runtime`."

        target = self.rt.target
        quiet = not self.verbose

        for addr, _ in self.breakpoints:
            addr_str = target.get_hex_str(addr)
            target.del_br(addr_str, quiet = quiet)
