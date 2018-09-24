__all__ = [
    "Watcher",
    "re_breakpoint_pos"
]

from os import (
    environ
)
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
    compile,
    split
)
from common import (
    notifier
)
from git import (
    Repo
)
from common.git_tools import (
    DiffParser
)

path.insert(0, join(dirname(abspath(__file__)), "..", "pyelftools"))

from elftools.common.intervalmap import (
    intervalmap
)

re_breakpoint_pos = compile("^[^:]*:[1-9][0-9]* [\w.]+$")


class LineVersionAdapter(object):
    def __init__(self, diff):
        self.delta_intervals = intervalmap()
        self.changes_intervals = intervalmap()
        self.diff_parser = DiffParser(diff)
        self.__delta = 0
        self.build_intervals()

    def __get_delta(self, old_range, new_range):
        if not bool(old_range.count) and not bool(new_range.count):
            return self.__delta
        elif not bool(old_range.count) and bool(new_range.count):
            if not new_range.count:
                self.__delta += 1
                return self.__delta
            else:
                # TODO: Do something
                return self.__delta
        elif bool(old_range.count) and not bool(new_range.count):
            if not old_range.count:
                self.__delta -= 1
                return self.__delta
            else:
                # TODO: Do something
                return self.__delta
        elif bool(old_range.count) and bool(new_range.count):
            if not old_range.count:
                self.__delta -= new_range.count
                return self.__delta
            elif not new_range.count:
                self.__delta += old_range.count
                return self.__delta
            else:
                self.__delta = (
                    self.__delta + old_range.count - new_range.count
            )
                return self.__delta

    def build_intervals(self):
        chunks = self.diff_parser.get_chunks()
        changes = self.diff_parser.get_changes()
        tmp_lineno = 1
        tmp_delta = 0

        for i in xrange(0, len(chunks)):
            old_range = chunks[i].old_file
            new_range = chunks[i].new_file

            if bool(new_range.count):
                self.changes_intervals[
                    new_range.lineno: new_range.lineno + (
                        new_range.count if new_range.count else 1
                    )
                ] = changes[i]
            else:
                self.changes_intervals[
                    new_range.lineno: new_range.lineno + 1
                ] = changes[i]

            self.delta_intervals[tmp_lineno: new_range.lineno] = tmp_delta
            tmp_delta = self.__get_delta(old_range, new_range)
            tmp_lineno = new_range.lineno

        self.delta_intervals[tmp_lineno: None] = tmp_delta

    def adapt_lineno(self, lineno):
        return lineno + self.delta_intervals[lineno]

    # def is_line_changed(self, lineno, epsilon = 0):
    #     res = True
    #
    #     for i in xrange(lineno - epsilon, lineno + epsilon + 1):
    #
    #         res = res and bool(self.)
    #
    #     return res

    def get_delta_intervals(self):
        return self.delta_intervals

    def get_changes_intervals(self):
        return self.changes_intervals


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
            file_name, line_str, version = (
                split("[: ]+", cb.__doc__.splitlines()[0])
            )
            line = int(line_str)
            repo = Repo(environ["QEMU_SRC"])
            commit = repo.commit(repo.head.object.hexsha)
            diff = commit.diff(version, file_name, True, unified = 0)
            if diff:
                line_adapter = LineVersionAdapter(diff[0].diff)
                line = line_adapter.adapt_lineno(line)
            line_map = dia.find_line_map(file_name)
            line_descs = line_map[line]
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
