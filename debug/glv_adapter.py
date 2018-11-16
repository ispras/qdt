__all__ = [
    "GitLineVersionAdapter"
]

from os.path import (
    isfile,
    sep
)
from git import (
    Repo
)
from re import (
    compile,
    S
)

from common import (
    DiffParser,
    intervalmap,
    lazy,
    trie_add,
    trie_find,
    PyGenerator
)
from debug import (
    LineAdapter
)

# TODO: comment it
re_version = compile("^\s+([\w\-.]*)$")
# TODO: comment it
EPS = 3


class Line2DeltaIntervalsBuilder(DiffParser):
    # TODO: comment it
    def __init__(self, diff):
        super(Line2DeltaIntervalsBuilder, self).__init__(diff)
        # self.delta_intervals = intervalmap()
        self._delta = 0
        self.delta_intervals()

    def _get_delta(self, old_range, new_range):
        # TODO: comment it
        if old_range.count is None and new_range.count is None:
            return self._delta, 0, 1
        elif old_range.count is None and new_range.count is not None:
            if not new_range.count:
                self._delta += 1
                return self._delta, 1, 1
            else:
                self._delta += 1 - new_range.count
                return self._delta, 0, new_range.count
        elif old_range.count is not None and new_range.count is None:
            if not old_range.count:
                self._delta -= 1
                return self._delta, 0, 1
            else:
                self._delta += old_range.count - 1
                return self._delta, 0, 1
        elif old_range.count is not None and new_range.count is not None:
            if not old_range.count:
                self._delta -= new_range.count
                return self._delta, 0, new_range.count
            elif not new_range.count:
                self._delta += old_range.count
                return self._delta, 1, 1
            else:
                self._delta += old_range.count - new_range.count
                return self._delta, 0, new_range.count

    @lazy
    def delta_intervals(self):
        # TODO: comment it
        intervals = intervalmap()
        tmp_lineno = 1
        tmp_delta = 0

        for chunk in self.iter_chunks():
            old_range = chunk.old_range
            new_range = chunk.new_range

            delta, right, left = self._get_delta(old_range, new_range)
            intervals[tmp_lineno: new_range.lineno + right] = tmp_delta
            tmp_lineno = new_range.lineno + left
            tmp_delta = delta

        intervals[tmp_lineno: None] = tmp_delta
        return intervals

    # def adapt_lineno(self, lineno):
    #     return lineno + self.delta_intervals[lineno]
    #
    # def ischanged_line(self, lineno, epsilon = 0):
    #     # TODO: do it better, add slice support to intervalmap
    #     for i in xrange(lineno - epsilon, lineno + epsilon + 1):
    #         if self.delta_intervals[i] is None:
    #             return True
    #     return False


class File2DeltaIntervals(dict):
    def __init__(self, *args, **kwargs):
        super(File2DeltaIntervals, self).__init__(*args, **kwargs)

    def __getitem__(self, key):
        if not isinstance(self[key], intervalmap):
            diff, _ = self[key]
            self.update({key:
                (Line2DeltaIntervalsBuilder(diff).delta_intervals, _)
            })

class GLVAdapterCache(dict):
    # TODO: comment it
    # def __init__(self, version, commit):
    def __init__(self, curr_commit, *args, **kwargs):
        self.curr_commit = curr_commit
        # self.del
        super(GLVAdapterCache, self).__init__(*args, **kwargs)

    def __getitem__(self, key):
        if key not in self:
            pass

    # def __setitem__(self, key, value):
    #     pass

    def version_diff_add(self, version, commit):
        diff = commit.diff(version, "*.c", True, unified = 0)
        if diff:
            for changes in diff:
                if changes.raw_rename_to:
                    val = (changes.diff, changes.raw_rename_to)
                else:
                    val = (changes.diff, None)
                if changes.a_rawpath:
                    file_name = changes.a_rawpath
                else:
                    file_name = changes.b_rawpath
                self.version_chunks_add(file_name, val)

    def version_chunks_add(self, file_name, chunks):
        trie_add(self.version_cache,
            tuple(reversed(file_name.split(sep))), chunks
        )

    def version_chunks_find(self, file_name):
        try:
            chunks = trie_find(self.version_cache,
                tuple(reversed(file_name.split(sep))
            ))
        except KeyError:
            return None, None
        else:
            return chunks


class CacheManager(object):
    def __init__(self, curr_version, curr_commit):
        self.curr_version = curr_version
        self.cache_file = "gdb_w_cache_{sha}.gwc".format(sha = curr_version)
        self.cache = GLVAdapterCache(curr_commit)

        if isfile(self.cache_file):
            with open(self.cache_file, "rb") as f:
                # cache =
                self.cache.update(cache)

        # if version in cache:
        #     self.version_cache = cache[version]
        # else:
        #     self.version_cache = cache[version] = dict()
        #     self.version_diff_add(version, commit)

    def __del__(self):
        with open(self.cache_file, "wb") as f:
            g = PyGenerator(backend = f)
            g.serialize(self.cache)

    # def store_cache(self, cache):
    #     with open(self.cache_file, "wb") as f:
    #         # dump(cache, f)
    #         pass
    #
    # def load_cache(self):
    #     with open(self.cache_file, "rb") as f:
    #         # return load(f)
    #         return


class GitLineVersionAdapter(LineAdapter):
    """ A line adapter class that implements line adaptation according with
'git diff' information.
"""
    def __init__(self, src_dir):
        repo = Repo(src_dir)
        curr_version = repo.head.object.hexsha
        self.curr_commit = repo.commit(curr_version)
        self.cm = CacheManager(curr_version, self.curr_commit)
        self.targets_cache = []

    @staticmethod
    def calc_lineno(delta_intervals, lineno):
        return lineno + delta_intervals[lineno]

    @staticmethod
    def ischanged_line_block(delta_intervals, lineno):
        # TODO: do it better, add slice support to intervalmap
        for i in xrange(lineno - EPS, lineno + EPS + 1):
            if delta_intervals[i] is None:
                return True
        return False

    def find_spoiling_commit(self, line, log, regexp):
        spoiling_commit = None

        for m in regexp.finditer(log):
            commit_diff = m.group(1)
            delta_intervals = (
                Line2DeltaIntervalsBuilder(commit_diff[40:]).delta_intervals
            )
            if self.ischanged_line_block(delta_intervals, line):
                spoiling_commit = commit_diff[:40]
            line = self.calc_lineno(delta_intervals, line)
        return spoiling_commit

    def do_exception(self):
        msg = []
        re_log = compile("<@>(.+?)</@>", flags = S)
        log_args = ("--pretty=format:</@><@>%H", "--no-merges", "-U0")

        for file_name, line, version, delta_intervals in self.targets_cache:
            log = self.curr_commit.repo.git.log(log_args,
                "HEAD..%s" % version, file_name, p = True
            )[4:] + "</@>"

            spoiling_commit = self.find_spoiling_commit(line, log, re_log)

            if spoiling_commit is None:
                log = self.curr_commit.repo.git.log(log_args,
                    ("%s..HEAD" % version, file_name), p = True
                )[4:] + "</@>"
                line = delta_intervals.adapt_lineno(line)
                spoiling_commit = self.find_spoiling_commit(line, log, re_log)

            msg.append(
                "\nmost damaging commit for '%s:%s %s': %s" %
                (file_name, line, version, spoiling_commit)
            )
        raise Exception('\n'.join(msg))

    def adapt_lineno(self, fname, lineno, _):
        version = re_version.match(_).groups()
        if version is not None:
            delta_intervals = self.cm.cache[version][fname](0)
            if self.ischanged_line_block(delta_intervals, lineno):
                self.targets_cache.append(
                    (fname, lineno, version, delta_intervals)
                )
                self.num_targets -= 1

                if not self.num_targets:
                    self.do_exception()

                return None
            return self.calc_lineno(delta_intervals, lineno)
        else:
            return lineno
