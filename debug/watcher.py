__all__ = [
    "Watcher"
  , "re_breakpoint_pos"
  , "is_breakpoint_cb"
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


re_breakpoint_pos = compile("^\s*([^:]*):([1-9][0-9]*)(\s?.*)$")


def is_breakpoint_cb(obj):
    """
    :returns: `True` if `obj` can be a breakpoint handler
    """
    if not ismethod(obj):
        return False
    if not obj.__name__.startswith("on_"):
        return False
    return bool(obj.__doc__)


@notifier("runtime_set")
class Watcher(object):
    """ Automates breakpoint setting with handlers. A breakpoint handler is a
method with name with prefix "on_" (see `is_breakpoint_cb`) and a position
specifier in the doc string. A position specifier is a tuple of file name and
line number. It should be given in next format (see `re_breakpoint_pos`):

    file/name/suffix.c:1234 an optional suffix separated by at least one space

    Because of suffix tree (a reversed trie) based search algorithm file may be
pointed by just _unique suffix_ of its name (not only by the full name).
Leading spaces are ignored.
    """

    def __init__(self, dic, verbose = False):
        """
    :type dic: DWARFInfoCache
        """
        self.dic = dic
        self.verbose = verbose

        # inspect methods getting those who is a breakpoint handler
        self.breakpoints = brs = []
        for name, cb in getmembers(type(self), predicate = is_breakpoint_cb):
            match = re_breakpoint_pos.match
            for l in cb.__doc__.splitlines():
                mi = match(l)
                if mi is not None:
                    break
            else:
                # No position specification was found. It's not a breakpoint
                # handler.
                continue

            file_name, line_str, _ = mi.groups()
            line_map = dic.find_line_map(file_name)
            line_descs = line_map[int(line_str)]

            for desc in line_descs:
                addr = desc.state.address
                brs.append((addr, getattr(self, name)))

    def init_runtime(self, rt):
        """ Setup breakpoint handlers
    :type rt: Runtime
        """

        v = self.verbose
        quiet = not v

        self.rt = rt
        target = rt.target

        for addr, cb in self.breakpoints:
            addr_str = target.get_hex_str(addr)

            if v:
                print("br 0x" + addr_str + ", handler = " + cb.__name__)

            target.add_br(addr_str, cb, quiet = quiet)

        self.__notify_runtime_set(rt)

    def remove_breakpoints(self):
        "Removes breakpoints assigned by `init_runtime`."

        target = self.rt.target
        quiet = not self.verbose

        for addr, cb in self.breakpoints:
            addr_str = target.get_hex_str(addr)
            target.remove_br(addr_str, cb, quiet = quiet)
