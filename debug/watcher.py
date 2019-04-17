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
    bstr,
    notifier
)
from .line_adapter import (
    IdentityAdapter
)


re_breakpoint_pos = compile("^\s*([^:]*):([1-9][0-9]*)(\s?.*)$")

def breakpoint_matches(lines, match = re_breakpoint_pos.match):
    for l in lines:
        mi = match(l)
        if mi is not None:
            yield mi

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

    def __init__(self, dic, line_adapter = None, verbose = False):
        """
    :type dic: DWARFInfoCache
    :param line_adapter:
        is object that specifically converts the line number of a file for some
        breakpoint position
        """
        self.dic = dic
        if line_adapter is None:
            line_adapter = IdentityAdapter()
        self.verbose = verbose

        # inspect methods getting those who is a breakpoint handler
        self.breakpoints = brs = []
        for _, cb in getmembers(self, predicate = is_breakpoint_cb):
            mi = None
            for mi in breakpoint_matches(cb.__doc__.splitlines()):
                file_name, lineno, opaque = mi.groups()
                raw_file_name = bstr(file_name)
                raw_file_name, line = line_adapter.adapt_lineno(
                    raw_file_name, lineno, opaque
                )
                if line is not None:
                    break
            else:
                if mi is None:
                    # No position specification was found.
                    # It's not a breakpoint handler.
                    continue
                raw_file_name, line = line_adapter.failback()

            line_map = dic.find_line_map(raw_file_name)
            line_descs = line_map[line]

            for desc in line_descs:
                addr = desc.state.address
                brs.append((addr, cb, raw_file_name, line))

    def init_runtime(self, rt):
        """ Setup breakpoint handlers
    :type rt: Runtime
        """

        v = self.verbose
        quiet = not v

        self.rt = rt
        target = rt.target

        for addr, cb, raw_file_name, line in self.breakpoints:
            addr_str = target.reg_fmt % addr

            if v:
                print("br 0x%s (%s:%d), handler = %s" % (
                    addr_str.decode("charmap"),
                    # XXX: encoding may be wrong but it's just a debug code
                    raw_file_name.decode("utf-8"),
                    line,
                    cb.__name__
                ))

            rt.add_br(addr_str, cb, quiet = quiet)

        self.__notify_runtime_set(rt)

    def remove_breakpoints(self):
        "Removes breakpoints assigned by `init_runtime`."

        rt = self.rt
        target = rt.target
        quiet = not self.verbose

        for addr, cb, _, _ in self.breakpoints:
            addr_str = target.reg_fmt % addr
            rt.remove_br(addr_str, cb, quiet = quiet)
