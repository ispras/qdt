__all__ = [
    "Watcher",
    "re_breakpoint_pos"
]

from os.path import (
    join,
    dirname,
    abspath
)
from sys import (
    path
)
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
from git import (
    Repo
)

path.insert(0, join(dirname(abspath(__file__)), "pyelftools"))

from elftools.common.intervalmap import (
    intervalmap
)

re_breakpoint_pos = compile("^[^:]*:[1-9][0-9]*$")

def get_delta_intervals(chunks):
    pass

def get_changed_intervals(c):
    pass


    def __get_delta(self, old_range, new_range):
        if len(old_range) == 1 and len(new_range) == 1:
            return self.__delta
        elif len(old_range) == 1 and len(new_range) != 1:
            if not int(new_range[1]):
                self.__delta += 1
                return self.__delta
            else:
                # TODO: Do something
                return self.__delta
        elif len(old_range) != 1 and len(new_range) == 1:
            if not int(old_range[1]):
                self.__delta -= 1
                return self.__delta
            else:
                # TODO: Do something
                return self.__delta
        elif len(old_range) != 1 and len(new_range) != 1:
            if not int(old_range[1]):
                self.__delta -= int(new_range[1])
                return self.__delta
            elif not int(new_range[1]):
                self.__delta += int(old_range[1])
                return self.__delta
            else:
                self.__delta = (
                    self.__delta + int(old_range[1]) - int(new_range[1])
            )
                return self.__delta

    def get_diffs(self):
        diff4search = intervalmap()
        diffdelta_intervals = intervalmap()
        old_lineno = 0
        delta = 0

        for chunk, changes in zip(self.chunks, self.changes):
            old, new = self.extract_ranges(chunk)

            if len(new) != 1:
                lineno, count = int(new[0]), int(new[1])
                diff4search[lineno: lineno + (count if count else 1)] = changes
            else:
                lineno = int(new[0])
                diff4search[lineno: lineno + 1] = changes

            diffdelta_intervals[old_lineno: lineno] = delta
            delta = self.__get_delta(old, new)
            old_lineno = lineno

        diffdelta_intervals[old_lineno: None] = delta

        return diff4search, diffdelta_intervals

    def get_new_lineno(self, old_lineno):
        return old_lineno + self.diffdelta_intervals[old_lineno]


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

            target.add_br(addr_str, cb, quiet = quiet)

        self.__notify_runtime_set(rt)

    def remove_breakpoints(self):
        "Removes breakpoints assigned by `init_runtime`."

        target = self.rt.target
        quiet = not self.verbose

        for addr, cb in self.breakpoints:
            addr_str = target.get_hex_str(addr)
            target.remove_br(addr_str, cb, quiet = quiet)
