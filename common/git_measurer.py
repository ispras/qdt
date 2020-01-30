__all__ = [
    "Measurer"
  # Measurement environments definitions
  , "py2"
  , "py3"
]


from .compat import (
    uname
)
from contextlib import (
    contextmanager
)
from .git_tools import (
    fast_repo_clone
)
from six.moves import (
    range
)
from shutil import (
    rmtree
)
from .lazy import (
    lazy
)
from traceback import (
    print_exc
)
from .cleaner import (
    get_cleaner
)


@contextmanager
def py2(ctx):
    ctx.interpreter = "python2"
    ctx.env_name = "py2"
    yield


@contextmanager
def py3(ctx):
    ctx.interpreter = "python3"
    ctx.env_name = "py3"
    yield


class Measurer(object):
    """ Given a `git.Repo` iterates versions (commits) from `base` to `current`
(inclusively). Each commit is measured using a protocol defined by those
methods:

    __enter__
    __version__
    __environment__
    __launch__
    __account__ or ___account_dict__
    __exit__

Where `__enter__` and `__exit__` are standard context manager interface.
Roles of those methods are described in base method implementations below.
    """

    def __init__(self, repo, current, base):
        self.repo = repo
        self.base, self.current = base, current
        self.clone_prefix = "repo"

        self.base_sha = repo.commit(base).hexsha
        self.current_sha = repo.commit(current).hexsha
        self.cleaner = get_cleaner()

    def __enter__(self):
        """ Called before any measuring. It MUST initialize and return a global
measurement context. The context is considered constant. It does depend no
neither environment nor version.
        """
        return self

    @contextmanager
    def __version__(self, global_context):
        """ A version context manager. It is used for each version tested.
It MUST initialize and yield a version context. Also, it can prepare OS
environment according to current version (`global_context.sha1`).

The `yield` instruction either raises exception from consequent stages or
simply returns control.
After that OS environment should be cleaned up.

Sequence number of current version in measurements queue is available in
`global_context.commit_number`.

Working directory of current version is cloned by the framework and
available at `global_context.clone` (`git.Repo`).
The framework also cleans the clone up by self.
However, the clone is preserved if an uncaught exception occurred.
The `__measure__` (see below) may also set `launch_context.error = True`.
        """
        try:
            # Do NOT yield `self` if simultaneous measurements are involved!
            yield self
        finally:
            "Do cleanup here."

        # Note, `try-finally` block is not necessary if no external resources
        # (like sockets or temporal files/directories) have been
        # acquired/created.

    @contextmanager
    def __environment__(self, version_context):
        """ An environment context manager.

Each version is measured under one or several environments. Each environment
is initialized by two context managers.

1. By one of `envs` of `measure` method (see below). Either standard or user
    defined, it sets those attributes of `version_context`:

    * `interpreter`
    * `env_name`

    See `py2` & `py3` implementations.

2. This one. It MUST yield an environment context which is used for each
measurement launch of current version. It also may configure OS environment
according to current measuring environment.

The `yield` instruction is utilized similarly (see `__version__` c. m. above).
        """
        try:
            yield self
        finally:
            "Do cleanup here."

    @contextmanager
    def __launch__(self, environment_context):
        """ A launch context. It is used for each measurement launch. It may
prepare OS environment for the launch. Because a launch may raise an exception,
OS environment cleaning up is strongly recommended to do here. It also must
yield a launch context.

Current launch number is available in `environment_context.launch_number`.

It may set `environment_context.break_request = True` to stop measurements for
current environment AFTER current launch.
        """

        try:
            yield self
        finally:
            "Do cleanup here."

    def __measure__(self, launch_context):
        """ A coroutine implemented as a generator. Given version, environment
& launch, it may perform measurements yielding results as name-value tuples.
A name MUST be keyword argument compatible.
After a measurement ended, a list of that tuples are passed to `__account__`.
Default `__account__` implementation converts the list to keyword arguments
and calls `__account_dict__`

It may set `launch_context.break_request = True` to stop measurements for
current environment.

Raised exception is caught by `yield` in `__launch__` (see above) and the
measurement is natively stopped.
        """

        yield "eaten", 0xdeadbeef
        yield "result", "death"
        yield "conclusion", 0xbadf00d

    def __account__(self, launch_context, *res):
        self.__account_dict__(launch_context, **dict(res))

    def __account_dict__(self, launch_context, **res):
        "Gets `res`ults yielded by `__measure__`."

    def measure(self, m_count = 5, envs = (py2, py3)):
        if m_count < 1:
            return

        self._internal_error = False
        machine = uname()

        with self as gctx:
            gctx.machine = machine

            for t, sha1 in enumerate(self.commit_queue):
                gctx.commit_number = t
                gctx.sha1 = sha1

                print("Checking %s out..." % sha1)
                print("\n".join(
                    (("> " + l) if l else ">") for l in
                        self.repo.commit(sha1).message.splitlines()
                    )
                )

                clone = fast_repo_clone(self.repo, sha1, self.clone_prefix)
                clean_task = self.cleaner.rmtree(clone.working_tree_dir)
                gctx.clone = clone

                try:
                    with self.__version__(gctx) as vctx:
                        errors = self._measure_version(vctx, envs, m_count)
                except:
                    errors = True
                    raise
                finally:
                    # allow user to work with bad version
                    if not errors or self._internal_error:
                        rmtree(clone.working_tree_dir)
                    self.cleaner.cancel(clean_task)

                if self._internal_error:
                    break

    def _measure_version(self, vctx, envs, m_count):
        errors = False
        for env in envs:
            with env(vctx):
                with self.__environment__(vctx) as ectx:
                    for i in range(m_count):
                        ectx.launch_number = i
                        break_request = False

                        with self.__launch__(ectx) as lctx:
                            lctx.break_request = False
                            lctx.errors = False

                            res = list(self.__measure__(lctx))

                        if lctx.break_request or ectx.break_request:
                            break_request = True
                        if lctx.errors:
                            errors = True

                        try:
                            self.__account__(lctx, *res)
                        except:
                            # Skip version
                            break_request = True
                            # end immediately exit `measure`
                            self._internal_error = True
                            print_exc()

                        if break_request:
                            break

        return errors

    @lazy
    def commit_queue(self):
        return tuple(reversed(list(self.commits) + [self.base_sha]))

    @property
    def commits(self):
        log = self.repo.git.rev_list(self.base_sha + ".." + self.current_sha)
        for l in log.split("\n"):
            yield l.strip()
