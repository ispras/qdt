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

QEMU_SRC = environ["QEMU_SRC"]


class LineVersionAdapter(object):
    def __init__(self, diff):
        self.diff_parser = DiffParser(diff)
        self.delta_intervals = intervalmap()
        self.changes_intervals = intervalmap()
        self.__delta = 0
        self.build_intervals()

    def __get_delta(self, old_range, new_range):
        if old_range.count is None and new_range.count is None:
            return self.__delta
        elif old_range.count is None and new_range.count is not None:
            if not new_range.count:
                self.__delta += 1
                return self.__delta
            else:
                # # TODO: Do something
                # raise AssertionError(
                #     ("gdb.watcher.LineVersionAdapter.__get_delta: "
                #      "not implemented case with (*) (*, * > 0)")
                # )
                self.__delta += 1 - new_range.count
                return self.__delta
        elif old_range.count is not None and new_range.count is None:
            if not old_range.count:
                self.__delta -= 1
                return self.__delta
            else:
                # # TODO: Do something
                # raise AssertionError(
                #     ("gdb.watcher.LineVersionAdapter.__get_delta: "
                #      "not implemented case with (*, * > 0) (*)")
                # )
                self.__delta += old_range.count - 1
                return self.__delta
        elif old_range.count is not None and new_range.count is not None:
            if not old_range.count:
                self.__delta -= new_range.count
                return self.__delta
            elif not new_range.count:
                self.__delta += old_range.count
                return self.__delta
            else:
                self.__delta += old_range.count - new_range.count
                return self.__delta

    def build_intervals(self):
        chunks_gen = self.diff_parser.get_chunks()
        changes_gen = self.diff_parser.get_changes()
        tmp_lineno = 1
        tmp_delta = 0

        for chunks, changes in zip(chunks_gen, changes_gen):
            old_range = chunks.old_file
            new_range = chunks.new_file

            if new_range.count is not None:
                self.changes_intervals[
                    new_range.lineno: new_range.lineno + (
                        new_range.count if new_range.count else 1
                    )
                ] = changes
            else:
                self.changes_intervals[
                    new_range.lineno: new_range.lineno + 1
                ] = changes

            self.delta_intervals[tmp_lineno: new_range.lineno] = tmp_delta
            tmp_delta = self.__get_delta(old_range, new_range)
            tmp_lineno = new_range.lineno

        self.delta_intervals[tmp_lineno: None] = tmp_delta

    def adapt_lineno(self, lineno):
        return lineno + self.delta_intervals[lineno]

    def get_line_changes(self, lineno, epsilon = 0):
        # TODO: do it better, add slice support to intervalmap
        changes = None

        for i in xrange(lineno - epsilon, lineno + epsilon + 1):
            changes = self.changes_intervals[i]
            if bool(changes):
                break
        return changes


def is_breakpoint_cb(object):
    if not ismethod(object):
        return False
    if not object.__name__.startswith("on_"):
        return False
    doc = object.__doc__
    lines_match = True
    for doc_line in doc.splitlines():
        lines_match = lines_match and bool(re_breakpoint_pos.match(doc_line))
    return bool(doc) and lines_match


@notifier("runtime_set")
class Watcher(object):

    def __init__(self, dia, verbose = True):
        self.dia = dia
        self.verbose = verbose

        # inspect methods getting those who is a breakpoint handler
        self.breakpoints = brs = []
        repo = Repo(QEMU_SRC)
        commit = repo.commit(repo.head.object.hexsha)
        for name, cb in getmembers(type(self), predicate = is_breakpoint_cb):
            err_msg = []
            line_map = None
            for doc_line in cb.__doc__.splitlines():
                file_name, line_str, version = (split("[: ]+", doc_line))
                line = int(line_str)
                diff = commit.diff(version, file_name, True, unified = 0)
                if diff:
                    line_adapter = LineVersionAdapter(diff[0].diff)
                    changes = line_adapter.get_line_changes(line, epsilon = 3)
                    if not bool(changes):
                        line = line_adapter.adapt_lineno(line)
                    else:
                        err_msg.append("%s %s:\n%s" % (
                            version, file_name, changes)
                        )
                        continue
                line_map = dia.find_line_map(file_name)
                line_descs = line_map[line]
                addr = line_descs[0].state.address
                brs.append((addr, getattr(self, name)))
            if not bool(line_map):
                raise Exception(
                    "br line adaption error:\n%s" % '\n'.join(err_msg)
                )

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
