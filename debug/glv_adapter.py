__all__ = [
    "GitLineVersionAdapter"
]

from os.path import (
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
                    # file renamed
                    val = (changes.diff, changes.a_rawpath)
                    fname = changes.b_rawpath
                else:
                    if changes.a_rawpath:
                        if changes.b_rawpath:
                            # file exists in both versions
                            fname = changes.a_rawpath
                            val = (changes.diff, None)
                        else:
                            # file exists only in current version
                            continue
                    else:
                        # file exists only in base version
                        fname = changes.b_rawpath
                        # for any lineno delta = None
                        val = (intervalmap(), None)
                trie_add(self.git_diffs[version],
                    tuple(reversed(fname.split(sep))), val
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
        self.cache_file = "glv_cache_{sha}.gwc".format(sha = curr_version)

        try:
            execfile(self.cache_file, {
                "cache_manager": self,
                "intervalmap": intervalmap,
                "GlvAdptrCache": GlvAdptrCache
            })
        except Exception:
            self.cache = GlvAdptrCache()

    def store_cache(self):
        pythonize(self.cache, self.cache_file)


class GitLineVersionAdapter(LineAdapter):
    """ A line adapter class that implements line adaptation according to
'git diff' information.
    """

    def __init__(self, src_dir):
        repo = Repo(src_dir)
        curr_version = repo.head.object.hexsha
        self.cm = GlvAdptrCacheManager(curr_version)
        self.curr_commit = repo.commit(curr_version)
        self.gdt = GitDiffsTrie(self.curr_commit)
        self.failures = []

    @staticmethod
    def calc_lineno(delta_intervals, lineno):
        return lineno + delta_intervals[lineno]

    @staticmethod
    def ischanged_line_block(delta_intervals, lineno, eps = 3):
        # TODO: do it better, add slice support to intervalmap

        # eps is value that defines unchanged line block
        try:
            eps = int(eps)
        except (TypeError, ValueError):
            eps = 3

        deltas = []

        for i in xrange(lineno - eps, lineno + eps + 1):
            if delta_intervals[i] is None:
                return True
            else:
                deltas.append(delta_intervals[i])
        if len(set(deltas)) != 1:
            return True
        return False

    def find_mung_commit(self, lineno, log, regexp):
        mung_commit = None

        for m in regexp.finditer(log):
            commit_diff = m.group(1)
            delta_intervals = git_diff2delta_intervals(commit_diff[40:])

            if self.ischanged_line_block(delta_intervals, lineno):
                mung_commit = commit_diff[:40]

            if delta_intervals[lineno] is not None:
                lineno = self.calc_lineno(delta_intervals, lineno)
            else:
                break
        return mung_commit

    def do_adapt(self, delta_intervals, lineno, eps):
        if not self.ischanged_line_block(delta_intervals, lineno, eps):
            return self.calc_lineno(delta_intervals, lineno)
        return None

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
            if version:
                delta_intervals, rename = self.get_glv_data(version, fname)
                if delta_intervals is not None:
                    new_lineno = self.do_adapt(delta_intervals, lineno, eps)

                    if new_lineno is None:
                        self.failures.append(
                            (fname, lineno, version, delta_intervals)
                        )
                    else:
                        self.failures[:] = []
                    return fname if rename is None else rename, new_lineno

        self.failures[:] = []
        return fname, lineno

    def failback(self):
        """ Raises exception and displays the closest mung commits for all
breakpoint positions.
"""
        msg = []
        re_log = compile("<@>(.+?)</@>", flags = S)
        log_args = ("--pretty=format:</@><@>%H", "--no-merges", "-U0")

        for fname, lineno, version, delta_intervals in self.failures:
            log = self.curr_commit.repo.git.log(log_args,
                "HEAD..%s" % version, fname, p = True
            )[4:] + "</@>"

            mung_commit = self.find_mung_commit(lineno, log, re_log)

            if mung_commit is None:
                if delta_intervals[lineno] is not None:
                    new_lineno = self.calc_lineno(delta_intervals, lineno)

                    log = self.curr_commit.repo.git.log(log_args,
                        "%s..HEAD" % version, fname, p = True
                    )[4:] + "</@>"

                    mung_commit = self.find_mung_commit(new_lineno, log,
                        re_log
                    )
                else:
                    msg.append((
                        "\nThe closest mung commit for '%s:%s %s' NOT FOUND!"
                        "\nTry decreasing the epsilon (default epsilon = 3)."
                        ) % (fname, lineno, version)
                    )
                    continue

            msg.append("\nThe closest mung commit for '%s:%s %s': %s" %
                (fname, lineno, version, mung_commit)
            )
        raise RuntimeError('\n'.join(msg))
