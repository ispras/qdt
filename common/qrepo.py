__all__ = [
    "QRepo"
  , "BuildDir"
  , "BuildDirFailure"
      , "ConfigureFailure"
      , "BuildFailure"
      , "InstallFailure"
]

from git import (
    Repo,
)
from multiprocessing import (
    Process,
)
from .git_tools import (
    init_submodules_from_cache,
)
from .workers import (
    PopenResult,
    PopenWorker,
)
from .extensible import (
    Extensible,
)
from os.path import (
    join,
    abspath,
    exists,
)
from .lazy import (
    lazy,
)
from .cli_args import (
    arg_list,
    configure_arg_list,
)
from .os_wrappers import (
    makedirs,
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
        self.build_dirs = {}

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
                join(self.qrepo.repo.working_tree_dir, ".git", "modules"),
            ),
            kwargs = dict(
                revert_urls = revert_urls
            )
        )
        p.start()

        while p.is_alive():
            yield False


class SavedResult(PopenResult):

    def __on_finish__(self, return_code, out_lines, err_lines):
        self.out = out_lines
        self.err = err_lines
        self.return_code = return_code

    def __str__(self):
        try:
            out, err, return_code = self.out, self.err, self.return_code
        except AttributeError:
            return "SavedResult: not finished"

        res = ["SavedResult:\n"]
        res.append("return code: %d\n" % return_code)
        if out:
            res.append("stdout:\n")
            res.extend(l.decode("unicode_escape") for l in out)
        else:
            res.append("stdout empty\n")

        if err:
            res.append("stderr:\n")
            res.extend(l.decode("unicode_escape") for l in err)
        else:
            res.append("stderr empty\n")

        return "".join(res)


class BuildDirFailure(Exception): pass

class ConfigureFailure(BuildDirFailure): pass
class BuildFailure(BuildDirFailure): pass
class InstallFailure(BuildDirFailure): pass


class BuildDir(object):

    def __init__(self, worktree,
        path = join("..", "build"),
        prefix = join("..", "install"),
        build_jobs = 4,
        extra_configure_args = dict(),
        extra_build_args = tuple(),
        extra_install_args = tuple(),
    ):
        self.worktree = worktree

        if path.startswith('.'):
            path = join(worktree.path, path)

        if prefix.startswith('.'):
            prefix = join(worktree.path, prefix)

        self.path =  abspath(path)
        self.prefix =  abspath(prefix)

        self.build_jobs = build_jobs

        self.extra_configure_args = configure_arg_list(extra_configure_args)
        self.extra_build_args = arg_list(extra_build_args,
            long_arg_prefix = "--",
        )
        self.extra_install_args = arg_list(extra_install_args,
            long_arg_prefix = "--",
        )

    @property
    def configure_args(self):
        ret = []
        ret.append("--prefix=" + self.prefix)
        ret.extend(self.extra_configure_args)
        return ret

    @property
    def build_args(self):
        ret = []
        if self.build_jobs:
            ret.append("-j")
            ret.append(str(self.build_jobs))
        ret.extend(self.extra_build_args)
        return ret

    @property
    def install_args(self):
        ret = list(self.extra_install_args)
        ret.append("install")
        return ret

    def need_configuration(self):
        # TODO: check extra_configure_args
        return not exists(join(self.path, "config.status"))

    def co_configure(self):
        if not self.need_configuration():
            return

        makedirs(self.path, exist_ok = True)

        configure = join(self.worktree.path, "configure")

        self.conf_result = res = SavedResult()

        yield PopenWorker(configure, *self.configure_args, cwd = self.path)(
            res
        )

        if res.return_code != 0:
            raise ConfigureFailure(res)

    def co_build(self):
        yield self.co_configure()

        self.build_result = res = SavedResult()

        yield PopenWorker("make", *self.build_args, cwd = self.path)(res)

        if res.return_code != 0:
            raise BuildFailure(res)

    def co_install(self):
        yield self.co_build()

        makedirs(self.prefix, exist_ok = True)

        self.instal_result = res = SavedResult()

        yield PopenWorker("make", *self.install_args, cwd = self.path)(res)

        if res.return_code != 0:
            raise InstallFailure(res)

    def __str__(self):
        return self.path


class QConfig(Extensible):

    def __init__(self, **settings):
        self.settings = settings
