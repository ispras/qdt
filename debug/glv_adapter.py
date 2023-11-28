__all__ = [
    "GitLineVersionAdapter"
]


from re import (
    compile,
    S
)
from git import (
    BadName,
    Repo
)
from six import (
    integer_types
)
from six.moves import (
    range
)
from common import (
    execfile,
    bstr,
    bsep,
    intervalmap,
    trie_add,
    trie_find,
    git_diff2delta_intervals,
    pythonize
)
from .line_adapter import (
    LineAdapter
)

# regular expression for git version of file and eps
re_glv_expr = compile("^(?:\s+([\w\-.]+))?(?:\s+(\d+)(?:\s|$))?")

identity_map = intervalmap()
identity_map[1:None] = 0

empty_map = intervalmap()


class GLVCacheManager(object):
    """ This class is helper that loads and stores a git line version cache.
It also gets git diff information, stores it in the trie and converts it into
git line version data.
    """

    class GLVCache(dict):
        """ It is trie that contains git line version data (delta intervals and
renaming for file name)
        """

        @staticmethod
        def __var_base__():
            return "glvcm._cache"

    def __init__(self, curr_commit):
        self.curr_commit = curr_commit
        self.cache_file = "glv_cache_{sha}.py".format(
            sha = curr_commit.hexsha
        )
        glob = {
            "glvcm": self,
            "intervalmap": intervalmap,
            "GLVCache": self.GLVCache
        }
        try:
            execfile(self.cache_file, glob)
        except Exception:
            self._cache = self.GLVCache()
        # trie that contains unhandled git diff information
        self._draft_diffs = {}

    def _add_git_diff(self, version):
        diff = self.curr_commit.diff(version, "*.c", True, unified = 0)
        self._draft_diffs[version] = {}

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
                        val = (None, None)
                trie_add(self._draft_diffs[version],
                    tuple(reversed(fname.split(bsep))), val
                )

    def _find_git_diff(self, version, fname):
        try:
            val, _ = trie_find(self._draft_diffs[version],
                tuple(reversed(fname.split(bsep)))
            )
        except KeyError:
            return identity_map, None
        else:
            diff, rename = val

            if diff is None:
                # File has been removed (see _add_git_diff)
                # and lineno can't be adapted (delta is None for any line).
                delta_map = empty_map
            else:
                # conversion of git diff information into delta intervals
                delta_map = git_diff2delta_intervals(diff)
            return (delta_map, rename)

    def get_glv_data(self, version, fname):
        "data is delta intervals and renaming for `fname`"

        version_trie = self._cache.setdefault(version, {})

        try:
            return trie_find(version_trie,
                tuple(reversed(fname.split(bsep)))
            )[0]
        except KeyError:
            pass

        if version not in self._draft_diffs:
            self._add_git_diff(version)

        val = self._find_git_diff(version, fname)
        trie_add(version_trie,
            tuple(reversed(fname.split(bsep))), val
        )
        return val

    def store_cache(self):
        pythonize(self._cache, self.cache_file)


class GitLineVersionAdapter(LineAdapter):
    """ A line adapter class that implements line adaptation according to
'git diff' information.
    """

    def __init__(self, repo):
        if not isinstance(repo, Repo):
            repo = Repo(repo)
        self.repo = repo
        curr_version = repo.head.object.hexsha
        self.curr_commit = repo.commit(curr_version)
        self.cm = GLVCacheManager(self.curr_commit)
        self.failures = []

    @staticmethod
    def calc_lineno(delta_intervals, lineno):
        return lineno + delta_intervals[lineno]

    @staticmethod
    def line_block_is_changed(delta_intervals, lineno, eps = None):
        # TODO: do it better, add slice support to intervalmap

        # eps is value that defines unchanged line block
        if eps is None:
            eps = 3
        elif not isinstance(eps, integer_types):
            eps = int(eps)

        deltas = set()

        for i in range(lineno - eps, lineno + eps + 1):
            if delta_intervals[i] is None:
                return True
            else:
                deltas.add(delta_intervals[i])

        if len(deltas) != 1:
            return True
        return False

    def find_obstructive_commit(self, lineno, log, regexp):
        obstructive_commit = None

        for m in regexp.finditer(log):
            commit_diff = m.group(1)
            delta_intervals = git_diff2delta_intervals(commit_diff[40:])

            if self.line_block_is_changed(delta_intervals, lineno):
                obstructive_commit = commit_diff[:40]

            if delta_intervals[lineno] is not None:
                lineno = self.calc_lineno(delta_intervals, lineno)
            else:
                break
        return obstructive_commit

    def do_adapt(self, delta_intervals, lineno, eps):
        if self.line_block_is_changed(delta_intervals, lineno, eps):
            return None
        else:
            return self.calc_lineno(delta_intervals, lineno)

    def adapt_lineno(self, fname, lineno, opaque):
        lineno = int(lineno)

        version, eps = re_glv_expr.match(opaque).groups()
        if version:
            try:
                self.repo.commit(version)
            except (ValueError, BadName):
                print("WARNING: '%s' commit doesn't exist" % version)
                return fname, None

            delta_intervals, rename = self.cm.get_glv_data(version, fname)
            fname = fname if rename is None else rename
            new_lineno = self.do_adapt(delta_intervals, lineno, eps)

            if new_lineno is not None:
                lineno = new_lineno
            else:
                self.failures.append(
                    (fname.decode("utf-8"), lineno, version, delta_intervals)
                )
                return fname, None

        self.failures[:] = []
        return fname, lineno

    def failback(self):
        """ Raises exception and displays the closest mung commits for all
breakpoint positions.
        """

        msg = []
        re_log = compile(b"<@>(.+?)</@>", flags = S)
        log_args = ("--pretty=format:</@><@>%H", "--no-merges", "-U0")

        for fname, lineno, version, delta_intervals in self.failures:
            log = self.curr_commit.repo.git.log(log_args,
                "HEAD..%s" % version, "--", fname, p = True
            )[4:] + "</@>"

            obstructive_commit = self.find_obstructive_commit(lineno,
                bstr(log), re_log
            )

            if obstructive_commit is None:
                if delta_intervals[lineno] is not None:
                    new_lineno = self.calc_lineno(delta_intervals, lineno)

                    log = self.curr_commit.repo.git.log(log_args,
                        "%s..HEAD" % version, "--", fname, p = True
                    )[4:] + "</@>"

                    obstructive_commit = self.find_obstructive_commit(
                        new_lineno, bstr(log), re_log
                    )
                else:
                    msg.append((
                        "\nThe closest obstructive commit for '%s:%s %s' "
                        "NOT FOUND!"
                        "\nTry decreasing the epsilon (default epsilon = 3)."
                        ) % (fname, lineno, version)
                    )
                    continue

            msg.append("\nThe closest obstructive commit for '%s:%s %s': %s" %
                (fname, lineno, version, obstructive_commit)
            )
        raise RuntimeError('\n'.join(msg))
