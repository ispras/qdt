from git import (
    Repo
)
from tempfile import (
    mkdtemp
)
from subprocess import (
    Popen
)
from os.path import (
    isfile,
    join,
    dirname
)
from shutil import (
    rmtree
)
from time import (
    time
)
from common import (
    execfile,
    pythonize
)
from matplotlib import (
    pyplot as plt
)
from math import (
    sqrt
)


class GitRepo(object):

    def __init__(self, path):
        self.path = path
        self.repo = Repo(path)

    @property
    def head(self):
        return self.repo.head.commit.hexsha

    def version(self, tree_ish):
        return self.repo.commit(tree_ish).hexsha

    def get_tmp_wc(self, version = None):
        if version is None:
            version = self.head
        else:
            version = self.version(version)

        tmp_wc = mkdtemp("-%s" % version)

        for cmd in [
            ["git", "clone", "-n", "-s", self.path, "."],
            ["git", "checkout", "-f", version]
        ]:

            p = Popen(cmd, cwd = tmp_wc)

            p.wait()

            if p.returncode:
                raise RuntimeError(
                    "Failed to checkout source: %s" % p.returncode
                )

        return tmp_wc

    def commits(self, tree_ish, early_tree_ish = None):
        version = self.version(tree_ish)
        if early_tree_ish is None:
            early = None
        else:
            early = self.version(early_tree_ish)

        log = self.repo.git.rev_list(early + ".." + version)
        for l in log.split("\n"):
            yield l.strip()


class PersistentContext(object):
    """ Given a file name, keeps its attributes in sync with the file.

Example:

with PersistentContext("my_file", glob = globals()) as ctx:
    do_something(ctx)

Note, `glob` is only required iff `PyGenerator` compatible types are used.

    """

    def __init__(self, file_name, glob = None):
        self.__file_name = file_name
        self.__globals = {} if glob is None else glob

    def _load(self):
        if isfile(self.__file_name):
            loaded = {}
            try:
                execfile(self.__file_name, self.__globals, loaded)
                self.__dict__.update(loaded["persistent_context"])
            except:
                pass

    def _save(self):
        pythonize(self, self.__file_name)

    def __iter__(self):
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            """
            if k.startswith("__"):
                continue
            if k.startswith("_%s__" % type(self).__name__):
                continue
            """

            yield k, v

    @property
    def _dict(self):
        return dict(iter(self))

    def __gen_code__(self, g):
        g.pprint(self._dict)

    def __var_base__(self):
        return "persistent_context"

    def __enter__(self):
        self._load()
        return self

    def __exit__(self, *_): # type, value, traceback
        self._save()


def measurements(pyelftools, ctx):
    M_COUNT = 0
    xcoords = []
    ycoords = []
    yerr = []

    for x, sha1 in enumerate(
        reversed(list(pyelftools.commits("lazy", "eliben/master")))
    ):
        if M_COUNT > 0:
            print("Measuring %s\n\n" % sha1)

            wc = pyelftools.get_tmp_wc(sha1)

            tox_prepare = Popen(["tox", "-e", "py27", "--notest"], cwd = wc)
            tox_prepare.wait()

            print("\n\n...\n\n")

            for i in range(M_COUNT):
                t0 = time()
                tox = Popen(["tox", "-e", "py27"], cwd = wc)
                tox.wait()
                t1 = time()

                total = t1 - t0

                print("\n\ntotal: %s\n\n" % total)

                ctx.res.setdefault(sha1, []).append((i, total, tox.returncode))

                if tox.returncode:
                    break

            ctx._save()

            rmtree(wc)

        xcoords.append(x)

        _sum = 0.0
        _len = 0

        for i, t, res in ctx.res[sha1]:
            if res: # failed
                continue

            _len += 1
            _sum += t

        _avg = _sum / _len

        _err = 0

        for _, t, res in ctx.res[sha1]:
            if res: # failed
                continue

            _err += (t - _avg) ** 2

        _err /= _len
        _err = sqrt(_err)

        ycoords.append(_avg)

        yerr.append(_err)

    plt.errorbar(xcoords, ycoords,
        yerr = yerr,
        # xerr, fmt, ecolor, elinewidth, capsize, barsabove, lolims, uplims, xlolims, xuplims, errorevery, capthick, hold, data
    )
    plt.grid()
    plt.show()

if __name__ == "__main__":
    pyelftools = GitRepo(
        join(dirname(dirname(__file__)), "debug", "pyelftools")
    )

    with PersistentContext("_test_pyelftool_results.py") as c:
        if not hasattr(c, "version"):
            c.version = 0.1
            if not hasattr(c, "res"):
                c.res = {}

        if c.version == 0.1:
            res = c.res

            # update previous measurements
            for v in res.values():
                for i, m in list(enumerate(v)):
                    if isinstance(m, float):
                        v[i] = (0, m, 0)

            c.version = 0.2
            c._save()

        measurements(pyelftools, c)
