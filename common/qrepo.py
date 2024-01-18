__all__ = [
    "QRepo"
]

from .extensible import (
    Extensible,
)
from .git_tools import (
    init_submodules_from_cache,
    iter_submodules_caches,
)
from .lazy import (
    lazy,
)
from .workers import (
    PopenResult,
    PopenWorker,
)

from git import (
    Repo,
)
from multiprocessing import (
    Process,
)
from os.path import (
    abspath,
)


def _nop(*_, **__):
    pass


class QRepo(object):

    def __init__(self, path):
        self.path = abspath(path)
        self.repo = Repo(path)
        self.worktrees = {}

    @lazy
    def worktree(self):
        return self.worktrees[self.path]

    def __str__(self):
        return self.path

    def co_get_worktrees(self, handler = _nop):
        return PopenWorker(
            "git", "worktree", "list", "--porcelain",
            cwd = self.path
        )(
            GitWorktreeListParser(self, handler)
        )

    def co_prune(self):
        return PopenWorker("git", "worktree", "prune", cwd = self.path)(
            PopenResult()
        )

    def co_create_worktree(self, directory,
        version = None,
        new_branch = None,
        callback = None
    ):
        directory = abspath(directory)

        if version:
            args = (directory, version)
        else:
            args = (directory,)

        kw = dict(f = True, insert_kwargs_after = "add")
        if new_branch:
            kw["b"] = new_branch

        self.repo.git.worktree("add", *args, **kw)

        if callback:

            def handler(wt):
                # skip other work trees
                if wt.path == directory:
                    callback(wt)

        else:
            handler = _nop

        yield self.co_get_worktrees(handler)


class GitWorktreeListParser(PopenResult):

    def __init__(self, qrepo, handler):
        self.qrepo = qrepo
        self.handler = handler
        self.attrs = {}

    def __on_stdout__(self, line):
        attrs = self.attrs

        stripped = line.rstrip()
        if stripped:
            # see `man git worktree`,  Porcelain Format
            attr_val = stripped.split(b" ", 1)
            attr = attr_val[0].decode("utf-8")
            try:
                val = attr_val[1]
            except IndexError:
                val = True
            attrs[attr] = val
        else: # end of worktree definition
            self.attrs = {}
            wts = self.qrepo.worktrees
            path = attrs.pop(u"worktree").decode("utf-8")
            try:
                wt = wts[path]
            except KeyError:
                wt = QWorkTree(
                    path,
                    self.qrepo,
                    **attrs
                )
                wts[path] = wt
            self.handler(wt)


class QWorkTree(Extensible):

    def __init__(self, path, qrepo, **kw):
        super(QWorkTree, self).__init__(**kw)
        self.path = path
        self.qrepo = qrepo
        self.repo = Repo(path)

    def __str__(self):
        return self.path

    def co_init_submodules_from_cache(self, revert_urls = True):
        # Backing `init_submodules_from_cache` relies on `git submodule update`
        # command which can be time consuming. So, converting
        # `init_submodules_from_cache` to a coroutine is not an option.
        # Truly parallel Process is used instead.
        p = Process(
            target = init_submodules_from_cache,
            args = (
                self.repo,
                list(iter_submodules_caches(self.qrepo.repo)),
            ),
            kwargs = dict(
                revert_urls = revert_urls
            )
        )
        p.start()

        while p.is_alive():
            yield False


class QBuildDir(object):

    def __init__(self, path, working_copy):
        self.path = path
        self.working_copy = working_copy


class QConfig(Extensible):

    def __init__(self, **settings):
        self.settings = settings
