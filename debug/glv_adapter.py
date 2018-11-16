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
    iter_chunks,
    intervalmap,
    trie_add,
    trie_find,
    pythonize
)
from debug import (
    LineAdapter
)

# Regular expression for git version of file
re_version = compile("^\s+([\w\-.]*)(\s?.*)$")
# EPS is value that defines unchanged line block
EPS = 3
CURRENT_COMMIT = None


def get_delta_intervals(diff):
    """
:param diff:
    is 'git diff' information between current version file and base version
    file
:returns:
    the line-to-delta intervalmap built from `diff`

    """
    intervals = intervalmap()
    lineno = 1
    delta = 0

    for chunk in iter_chunks(diff):
        curr_range = chunk.curr_range
        base_range = chunk.base_range

        # `inclusive`: 0 - exclude `lineno` from current interval
        #              1 - include `lineno` in current interval
        #
        # `gap_size` - the size of gap between the current and next intervals
        #
        if base_range.count:
            # add a gap including `lineno`
            inclusive, gap_size = 0, base_range.count
        else:
            # include `lineno` in `intervals`
            inclusive, gap_size = 1, 1

        # The current interval
        intervals[lineno: base_range.lineno + inclusive] = delta

        # Calculate the left boundary for the next interval
        lineno = base_range.lineno + gap_size
        # Calculate the delta for the next interval
        delta += curr_range.count - base_range.count

    # The last interval
    intervals[lineno: None] = delta

    return intervals


class Fname2DeltaIntrvls(dict):
    """ This class is a trie, it converts 'git diff' information to a delta
intervalmap when it is accessed.
    """

    def __getitem__(self, fname):
        if stack()[1][3] == "adapt_lineno":
            # 'dict(self)' is used to exclude '__getitem__' call in 'trie_find'
            val, tail = self.find_val(dict(self), fname)

            # Convert 'git diff' chunks to a line-to-delta intervalmap.
            if val[0] and not isinstance(val[0], intervalmap):
                diff, rename = val
                val = (get_delta_intervals(diff), rename)
                trie_add(self,
                    tuple(reversed(fname.split(sep))) + tail, val,
                    replace = True
                )
            return val
        else:
            return super(Fname2DeltaIntrvls, self).__getitem__(fname)

    @staticmethod
    def find_val(trie, fname):
        """
    :returns:
        value found in `trie` and prefix tail for `fname`

        """
        try:
            val, tail = trie_find(trie, tuple(reversed(fname.split(sep))))
        except KeyError:
            return (None, None), None
        else:
            return val, tail


class GLVAdapterCache(dict):
    """ This class is a line version cache whose value is trie, it adds git
diff if base version not yet in cache.
    """

    def __getitem__(self, version):
        try:
            value = super(GLVAdapterCache, self).__getitem__(version)
        except KeyError:
            value = self.add_version_diff(version)
        return value

    @staticmethod
    def __var_base__():
        return "cache_manager.cache"

    def add_version_diff(self, version):
        diff = CURRENT_COMMIT.diff(version, "*.c", True, unified = 0)
        trie = Fname2DeltaIntrvls()

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

        return trie


class CacheManager(object):
    """ This class is manager that loads and stores a line version cache. """

    def __init__(self, curr_version):
        self.cache_file = "gdb_w_cache_{sha}.gwc".format(sha = curr_version)
        self.is_empty_load = False

        if isfile(self.cache_file):
            execfile(self.cache_file, {
                "cache_manager": self,
                "GLVAdapterCache": GLVAdapterCache,
                "Fname2DeltaIntrvls": Fname2DeltaIntrvls,
                "intervalmap": intervalmap
            })
            if not self.cache:
                self.is_empty_load = True
        else:
            self.cache = GLVAdapterCache()

    def store_cache(self):
        if self.cache:
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
        self.failures = []

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

    def find_mung_commit(self, line, log, regexp):
        mung_commit = None

        for m in regexp.finditer(log):
            commit_diff = m.group(1)
            delta_intervals = (get_delta_intervals(commit_diff[40:]))
            if self.ischanged_line_block(delta_intervals, line):
                mung_commit = commit_diff[:40]
            line = self.calc_lineno(delta_intervals, line)
        return mung_commit

    def adapt_lineno(self, fname, lineno, opaque):
        lineno = int(lineno)

        if opaque:
            version, _ = re_version.match(opaque).groups()

            if version is not None:
                if not self.cm.is_empty_load:
                    delta_intervals, rename = self.cm.cache[version][fname]
                    if rename:
                        fname = rename
                else:
                    delta_intervals = None

                if delta_intervals is not None:
                    if self.ischanged_line_block(delta_intervals, lineno):
                        self.failures.append(
                            (fname, lineno, version, delta_intervals)
                        )
                        return fname, None
                    else:
                        return fname, self.calc_lineno(delta_intervals, lineno)
        return fname, lineno

    def failback(self):
        """ Raises exception and displays the closest mung commits for all
breakpoint positions.
"""
        msg = []
        re_log = compile("<@>(.+?)</@>", flags = S)
        log_args = ("--pretty=format:</@><@>%H", "--no-merges", "-U0")

        for fname, line, version, delta_intervals in self.failures:
            log = CURRENT_COMMIT.repo.git.log(log_args,
                "HEAD..%s" % version, fname, p = True
            )[4:] + "</@>"

            mung_commit = self.find_mung_commit(line, log, re_log)

            if mung_commit is None:
                log = CURRENT_COMMIT.repo.git.log(log_args,
                    ("%s..HEAD" % version, fname), p = True
                )[4:] + "</@>"
                line = delta_intervals.adapt_lineno(line)
                mung_commit = self.find_mung_commit(line, log, re_log)

            msg.append(
                "\nthe closest mung commit for '%s:%s %s': %s" %
                (fname, line, version, mung_commit)
            )
        raise RuntimeError('\n'.join(msg))
