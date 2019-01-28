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
    git_diff2delta_intervals,
    intervalmap,
    trie_add,
    trie_find,
    pythonize
)
from debug import (
    LineAdapter
)

# regular expression for git version of file and eps
re_glv_expr = compile("^(?:\s+([\w\-.]+))?(?:\s+(\d+))?(\s?.*)$")


class GitDiffsTrie(object):
    """ This class gets git diff information and stores it in the trie.
It also finds git diff information in the trie and converts it into delta
intervals.
    """

    def __init__(self, curr_commit):
        self.curr_commit = curr_commit
        # trie that contains git diff information
        self.git_diffs = {}

    def add_git_diff(self, version):
        diff = self.curr_commit.diff(version, "*.c", True, unified = 0)
        self.git_diffs[version] = {}

        if diff:
            for changes in diff:
                if changes.raw_rename_to:
                    val = (changes.diff, changes.raw_rename_to)
                    # "new" file name is the name of the file at base version
                    # TODO: file_name = changes.b_rawpath
                else:
                    val = (changes.diff, None)
                    # if b_rawpath:
                    #     file_name = b_rawpath
                    # else:
                    #     does this file exist in base version?
                if changes.a_rawpath:
                    file_name = changes.a_rawpath
                else:
                    file_name = changes.b_rawpath
                trie_add(self.git_diffs[version],
                    tuple(reversed(file_name.split(sep))), val
                )

    def find_git_diff(self, version, fname):
        try:
            val, _ = trie_find(self.git_diffs[version],
                tuple(reversed(fname.split(sep)))
            )
        except KeyError:
            return None, None
        else:
            if val[0] and not isinstance(val[0], intervalmap):
                diff, rename = val
                # conversion of git diff information into delta intervals
                val = (git_diff2delta_intervals(diff), rename)
            return val


class GlvAdptrCache(dict):
    """ It is trie that contains git line version data (delta intervals and
renaming for file name)
    """
    @staticmethod
    def __var_base__():
        return "cache_manager.cache"


class GlvAdptrCacheManager(object):
    """ This class is manager that loads and stores a line version cache. """

    def __init__(self, curr_version):
        # It is not GDB. line_cache_{sha}?
        self.cache_file = "gdb_w_cache_{sha}.gwc".format(sha = curr_version)

        if isfile(self.cache_file):
            # XXX: what about bad file (an exception)? Should we create an
            # empty cache?
            execfile(self.cache_file, {
                "cache_manager": self,
                "intervalmap": intervalmap,
                "GlvAdptrCache": GlvAdptrCache
            })
        else:
            self.cache = GlvAdptrCache()

    def store_cache(self):
        pythonize(self.cache, self.cache_file)


class GitLineVersionAdapter(LineAdapter):
# TODO: "according to" ?
    """ A line adapter class that implements line adaptation according with
'git diff' information.
"""
# TODO: """ indent

    def __init__(self, src_dir):
        repo = Repo(src_dir)
        curr_version = repo.head.object.hexsha
        self.cm = GlvAdptrCacheManager(curr_version)
        self.curr_commit = repo.commit(curr_version)
        self.gdt = GitDiffsTrie(self.curr_commit)
        # eps is value that defines unchanged line block
        self.eps = 3
        self.failures = []

    @staticmethod
    def calc_lineno(delta_intervals, lineno):
        return lineno + delta_intervals[lineno]

    def ischanged_line_block(self, delta_intervals, lineno):
        # TODO: do it better, add slice support to intervalmap
        deltas = []

        for i in xrange(lineno - self.eps, lineno + self.eps + 1):
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
            delta_intervals = git_diff2delta_intervals(commit_diff[40:])

            if self.ischanged_line_block(delta_intervals, line):
                mung_commit = commit_diff[:40]

            try:
                line = self.calc_lineno(delta_intervals, line)
            except TypeError:
                # if lineno for next commit not calculated then this commit
                # is the closest mung commit
                mung_commit = commit_diff[:40]
                break
        return mung_commit

    def get_glv_data(self, version, fname):
        try:
            return trie_find(self.cm.cache[version],
                tuple(reversed(fname.split(sep)))
            )[0]
        except KeyError:
            if version not in self.cm.cache:
                self.cm.cache[version] = {}
                self.gdt.add_git_diff(version)
            elif version not in self.gdt.git_diffs:
                self.gdt.add_git_diff(version)

            val = self.gdt.find_git_diff(version, fname)
            trie_add(self.cm.cache[version],
                tuple(reversed(fname.split(sep))), val
            )
            return val

    def adapt_lineno(self, fname, lineno, opaque):
        lineno = int(lineno)

        if opaque:
            version, eps, _ = re_glv_expr.findall(opaque)[0]
            if eps:
                self.eps = int(eps)

            if version:
                delta_intervals, rename = self.get_glv_data(version, fname)
                if rename is not None:
                    fname = rename

                if delta_intervals is not None:
                    if not self.ischanged_line_block(delta_intervals, lineno):
                        return fname, self.calc_lineno(delta_intervals, lineno)
                    else:
                        self.failures.append(
                            (fname, lineno, version, delta_intervals)
                        )
                        return fname, None
        return fname, lineno

    def failback(self):
        """ Raises exception and displays the closest mung commits for all
breakpoint positions.
"""
        msg = []
        re_log = compile("<@>(.+?)</@>", flags = S)
        log_args = ("--pretty=format:</@><@>%H", "--no-merges", "-U0")

        for fname, line, version, delta_intervals in self.failures:
            log = self.curr_commit.repo.git.log(log_args,
                "HEAD..%s" % version, fname, p = True
            )[4:] + "</@>"

            mung_commit = self.find_mung_commit(line, log, re_log)

            if mung_commit is None:
                log = self.curr_commit.repo.git.log(log_args,
                    ("%s..HEAD" % version, fname), p = True
                )[4:] + "</@>"
                line = self.calc_lineno(delta_intervals, line)
                mung_commit = self.find_mung_commit(line, log, re_log)

            msg.append(
                "\nthe closest mung commit for '%s:%s %s': %s" %
                (fname, line, version, mung_commit)
            )
        raise RuntimeError('\n'.join(msg))
