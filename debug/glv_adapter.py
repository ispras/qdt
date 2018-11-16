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
from inspect import (
    stack
)

from common import (
    DiffParser,
    intervalmap,
    trie_add,
    trie_find,
    pythonize
)
from debug import (
    LineAdapter
)

# Regular expression for git version of file
re_version = compile("^\s+([\w\-.]*)$")
# EPS is value that defines unchanged line block
EPS = 3
CURRENT_COMMIT = None


class Line2DeltaIntervalsBuilder(DiffParser):
    """ This class builds line-to-delta intervalmap by git diff. """
    def __init__(self, diff):
        super(Line2DeltaIntervalsBuilder, self).__init__(diff)
        self._delta = 0

    def _get_delta(self, old_range, new_range):
        """ Returns calculated delta and adjustments for bounds of the current
and next intervals.
        """
        if old_range.count is None:
            if new_range.count is None:
                return self._delta, 0, 1
            else:
                if not new_range.count:
                    self._delta += 1
                    return self._delta, 1, 1
                else:
                    self._delta += 1 - new_range.count
                    return self._delta, 0, new_range.count
        else:
            if new_range.count is None:
                if not old_range.count:
                    self._delta -= 1
                    return self._delta, 0, 1
                else:
                    self._delta += old_range.count - 1
                    return self._delta, 0, 1
            else:
                if not old_range.count:
                    self._delta -= new_range.count
                    return self._delta, 0, new_range.count
                elif not new_range.count:
                    self._delta += old_range.count
                    return self._delta, 1, 1
                else:
                    self._delta += old_range.count - new_range.count
                    return self._delta, 0, new_range.count

    def delta_intervals(self):
        """ Returns a line-to-delta intervalmap built from git diff. """
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


class Fname2Chunks(dict):
    """ This is a trie whose values are git diff chunks. """
    def __init__(self, *args, **kwargs):
        super(Fname2Chunks, self).__init__(*args, **kwargs)

    def __getitem__(self, fname):
        if stack()[1][3] == "adapt_lineno":
            val, tail = self.chunks_find(self.copy(), fname)

            # Convert git diff chunks to a line-to-delta intervalmap.
            if val[0] and not isinstance(val[0], intervalmap):
                diff, rename = val
                val = (Line2DeltaIntervalsBuilder(diff).delta_intervals(),
                    rename
                )
                trie_add(self,
                    tuple(reversed(fname.split(sep))) + tail, val,
                    replace = True
                )
            return val[0]
        else:
            return super(Fname2Chunks, self).__getitem__(fname)

    @staticmethod
    def chunks_find(trie, file_name):
        try:
            val, tail = trie_find(trie, tuple(reversed(file_name.split(sep))))
        except KeyError:
            return (None, None), None
        else:
            return val, tail

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.pprint(self)
        gen.gen_end()


class GLVAdapterCache(dict):
    """ This class is a line version cache. """
    def __init__(self, *args, **kwargs):
        super(GLVAdapterCache, self).__init__(*args, **kwargs)

    def __getitem__(self, version):
        try:
            value = super(GLVAdapterCache, self).__getitem__(version)
        except KeyError:
            value = self.version_diff_add(version)
        return value

    @staticmethod
    def __var_base__():
        return "self.cache"

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.write('{')
        for attr, val in self.items():
            gen.gen_field('"' + attr + '": ' + gen.nameof(val))
        gen.gen_end("})")

    def version_diff_add(self, version):
        diff = CURRENT_COMMIT.diff(version, "*.c", True, unified = 0)
        trie = Fname2Chunks()

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
                trie_add(trie, tuple(reversed(file_name.split(sep))), val)
            self.update({version: trie})

            return self[version]
        return trie


class CacheManager(object):
    """ This class is manager that loads and stores a line version cache. """
    def __init__(self, curr_version):
        self.cache_file = "gdb_w_cache_{sha}.gwc".format(sha = curr_version)
        self.is_empty_load = False

        if isfile(self.cache_file):
            execfile(self.cache_file, {
                "self": self,
                "GLVAdapterCache": GLVAdapterCache,
                "Fname2Chunks": Fname2Chunks,
                "intervalmap": intervalmap
            })
            if not self.cache:
                self.is_empty_load = True
        else:
            self.cache = GLVAdapterCache()

    def store_cache(self):
        pythonize(self.cache, self.cache_file)


class GitLineVersionAdapter(LineAdapter):
    """ A line adapter class that implements line adaptation according with
'git diff' information.
"""
    def __init__(self, src_dir):
        repo = Repo(src_dir)
        curr_version = repo.head.object.hexsha
        global CURRENT_COMMIT
        CURRENT_COMMIT = repo.commit(curr_version)
        self.cm = CacheManager(curr_version)
        self.fails_cache = []

    @staticmethod
    def calc_lineno(delta_intervals, lineno):
        return lineno + delta_intervals[lineno]

    @staticmethod
    def ischanged_line_block(delta_intervals, lineno):
        # TODO: do it better, add slice support to intervalmap
        deltas = []

        for i in xrange(lineno - EPS, lineno + EPS + 1):
            if delta_intervals[i] is None:
                return True
            else:
                deltas.append(delta_intervals[i])
        if len(set(deltas)) != 1:
            return True
        return False

    def find_spoiling_commit(self, line, log, regexp):
        spoiling_commit = None

        for m in regexp.finditer(log):
            commit_diff = m.group(1)
            delta_intervals = (
                Line2DeltaIntervalsBuilder(commit_diff[40:]).delta_intervals()
            )
            if self.ischanged_line_block(delta_intervals, line):
                spoiling_commit = commit_diff[:40]
            line = self.calc_lineno(delta_intervals, line)
        return spoiling_commit

    def adapt_lineno(self, fname, lineno, opaque):
        lineno = int(lineno)

        if opaque:
            version = re_version.match(opaque).groups()[0]

            if version is not None:
                if not self.cm.is_empty_load:
                    delta_intervals = self.cm.cache[version][fname]
                else:
                    delta_intervals = None

                if delta_intervals is not None:
                    if self.ischanged_line_block(delta_intervals, lineno):
                        self.fails_cache.append(
                            (fname, lineno, version, delta_intervals)
                        )
                        return fname, None
                    else:
                        return fname, self.calc_lineno(delta_intervals, lineno)
        return fname, lineno

    def failback(self):
        """ Raises exception and displays the closest spoiling commits for all
breakpoint positions.
"""
        msg = []
        re_log = compile("<@>(.+?)</@>", flags = S)
        log_args = ("--pretty=format:</@><@>%H", "--no-merges", "-U0")

        for file_name, line, version, delta_intervals in self.fails_cache:
            log = CURRENT_COMMIT.repo.git.log(log_args,
                "HEAD..%s" % version, file_name, p = True
            )[4:] + "</@>"

            spoiling_commit = self.find_spoiling_commit(line, log, re_log)

            if spoiling_commit is None:
                log = CURRENT_COMMIT.repo.git.log(log_args,
                    ("%s..HEAD" % version, file_name), p = True
                )[4:] + "</@>"
                line = delta_intervals.adapt_lineno(line)
                spoiling_commit = self.find_spoiling_commit(line, log, re_log)

            msg.append(
                "\nmost damaging commit for '%s:%s %s': %s" %
                (file_name, line, version, spoiling_commit)
            )
        raise RuntimeError('\n'.join(msg))
