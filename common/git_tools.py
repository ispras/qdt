__all__ = [
    "GGB_IBY"
  , "CommitDesc"
  , "iter_chunks"
  , "git_diff2delta_intervals"
  , "fast_repo_clone"
  , "git_find_commit"
  , "init_submodules_from_cache"
  , "repo_path_in_tree"
  , "iter_submodules_caches"
]

from collections import (
    namedtuple
)
from re import (
    compile
)
from .intervalmap import (
    intervalmap
)
from tempfile import (
    mkdtemp
)
from os.path import (
    sep,
    exists,
    join
)
from git import (
    BadName,
    GitCommandError,
    Repo
)
from time import (
    time
)
from itertools import (
    count
)


# Iterations Between Yields of Git Graph Building task
GGB_IBY = 100

# Unified Diff Format:
# https://www.artima.com/weblogs/viewpost.jsp?thread=164293
Range = namedtuple("Range", "lineno count")
# 'old' - range removed from previous version of file
# 'new' - range added to new version of file
Chunk = namedtuple("Chunk", "old new")

re_chunks = compile(b"@@ -(\d+)(?:,?(\d*)) \+(\d+)(?:,?(\d*)) @@")


def iter_chunks(diff):
    for chunk in re_chunks.findall(diff):
        c_lineno, c_count, b_lineno, b_count = chunk
        yield Chunk(
            # empty '*_count' is equivalent to '*_count' == 1
            Range(int(c_lineno), int(c_count) if c_count != b'' else 1),
            Range(int(b_lineno), int(b_count) if b_count != b'' else 1)
        )


def git_diff2delta_intervals(diff):
    """
:param diff:
    is 'git diff' information between current version of file and base version
    of file
:returns:
    the line-to-delta intervalmap built from `diff`

    """
    intervals = intervalmap()
    lineno = 1
    delta = 0

    for chunk in iter_chunks(diff):
        # diff is reversive, i.e. how to get the base version from a current.
        curr_range = chunk.old
        base_range = chunk.new

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

        # current interval
        intervals[lineno: base_range.lineno + inclusive] = delta

        # calculate the left boundary for the next interval
        lineno = base_range.lineno + gap_size
        # calculate the delta for the next interval
        delta += curr_range.count - base_range.count

    # default interval if diff is empty and last interval otherwise
    intervals[lineno: None] = delta

    return intervals


class CommitDesc(object):

    def __init__(self, sha, parents = None, children = None):
        self.sha = sha
        self.parents = [] if parents is None else parents
        self.children = [] if children is None else children

        # serial number according to the topological sorting
        self.num = None

    def add_child(self, cd):
        self.children.append(cd)
        cd.parents.append(self)

    def add_parent(self, cd):
        cd.add_child(self)

    @classmethod
    def co_build_git_graph(klass, repo, commit_desc_nodes):
        repo_commit = repo.commit

        t0 = time()
        # iterations to yield
        i2y = GGB_IBY

        # enumeration according to the topology sorting
        n = count(0)
        # to_enum is used during the enumeration
        # it contains commit to enumerate
        to_enum = None
        # build_stack contains edges represented by tuples
        # (parent, child), where parent is instance of
        # git.Commit, child is instance of `klass` (e.g., QemuCommitDesc)
        build_stack = []
        for head in repo.references:
            head_commit = head.commit
            head_commit_hexsha = head_commit.hexsha
            # skip processed heads
            if head_commit_hexsha in commit_desc_nodes:
                continue

            head_desc = klass(head_commit_hexsha, [], [])
            commit_desc_nodes[head_commit_hexsha] = head_desc
            # add edges connected to head being processed
            for p in head_commit.parents:
                build_stack.append((p, head_desc))

            while build_stack:
                parent, child_commit_desc = build_stack.pop()
                parent_hexsha = parent.hexsha

                parent_desc = commit_desc_nodes.get(parent_hexsha, None)

                if parent_desc is None:
                    parent_desc = klass(parent_hexsha, [], [child_commit_desc])
                    commit_desc_nodes[parent_hexsha] = parent_desc

                    if parent.parents:
                        for p in parent.parents:
                            build_stack.append((p, parent_desc))
                    else:
                        # current edge parent is an elder commit in the tree,
                        # that is why we should enumerate starting from it
                        to_enum = parent_desc
                else:
                    # the existence of parent_desc means that parent has been
                    # enumerated before. Hence, we starts enumeration from
                    # it's child
                    to_enum = child_commit_desc
                    parent_desc.children.append(child_commit_desc)

                child_commit_desc.parents.append(parent_desc)

                if i2y <= 0:
                    yield True
                    i2y = GGB_IBY
                else:
                    i2y -= 1

                # numbering is performed from the 'to_enum' to either a leaf
                # commit or a commit just before a merge which have at least
                # one parent without number (except the commit)
                while to_enum is not None:
                    e = to_enum
                    to_enum = None
                    # if the number of parents in the commit_desc_nodes
                    # is equal to the number of parents in the repo,
                    # then all parents were numbered (added) earlier
                    # according to the graph building algorithm,
                    # else we cannot assign number to the commit yet
                    if len(e.parents) == len(repo_commit(e.sha).parents):
                        e.num = next(n)
                        # according to the algorithm, only one child
                        # have no number. Other children either have
                        # been enumerated already or are not added yet
                        for c in e.children:
                            if c.num is None:
                                to_enum = c
                                break

                    if i2y <= 0:
                        yield True
                        i2y = GGB_IBY
                    else:
                        i2y -= 1

        t1 = time()
        print("co_build_git_graph work time " + str(t1 - t0))


def fast_repo_clone(repo, version = None, prefix = "repo"):
    """ Creates Git repository clone with working copy in temporal directory
as fast as possible. A clone is neither honest nor independent, so be careful.
    """
    if version is None:
        version = repo.head.commit.hexsha
    else:
        version = git_find_commit(repo, version).hexsha

    tmp_wc = mkdtemp(prefix = "%s-%s-" % (prefix, version))

    # Current approach uses "-s" (--shared) option to avoid copying
    # of history and "-n" (--no-checkout) to avoid redundant checking
    # out of repo's HEAD in the new clone. Requested version is checked out
    # explicitly. Therefore, overhead of cloning is low enough.
    new_repo = repo.clone(tmp_wc, no_checkout = True, shared = True)

    git = new_repo.git

    git.checkout(version, force = True)

    # Submodules also are recursively initialized. But straightforward
    # invocation of of "update --init" command will result in downloading of
    # submodules history. Instead, submodules URLs are redirected to local
    # history copies inside original repo (if exist). As a result, submodules
    # initialization is done without redundant copying.
    # However! ".gitmodules" file is considered changed by Git because of that
    # redirection.

    init_submodules_from_cache(new_repo, list(iter_submodules_caches(repo)))

    return new_repo


def iter_submodules_caches(repo):
    modules = join(repo.git_dir, "modules")
    yield modules

    # Note, a `repo` can be a "worktree". Worktree's `repo.working_tree_dir`
    # contains ".git" file with path to a special directory (it's
    # `repo.git_dir`) within the main clone repository.
    # E.g. "/main/clone/path/.git/worktrees/worktree_name/".
    # The special directory contains modules cache in "modules" directory.
    # A main clone contains "modules" cache directory in ".git" (which is
    # `repo.common_dir`).

    if repo.common_dir:
        next_modules = join(repo.common_dir, "modules")
        if next_modules != modules:
            yield next_modules
        # else:
        #    it's not a worktree; likely, normal repo


def init_submodules_from_cache(repo, cache_dirs, revert_urls = False):
    git = repo.git

    if not exists(join(repo.working_tree_dir, ".gitmodules")):
        # Has no modules
        return

    # see: https://bugs.launchpad.net/ubuntu/+source/git/+bug/1993586
    try:
        # Note, --local is not enough.
        prev_protocol_file_allow = git.config(
            "--global", "protocol.file.allow"
        )
    except GitCommandError as e:
        # If value is not set, git normally returns error code (1).
        # But we use weaker condition: only check stderr/out
        if e.stderr or e.stdout: # or e.status != 1:
            raise
        prev_protocol_file_allow = None

    if prev_protocol_file_allow != "always":
        git.config("--global", "protocol.file.allow", "always")

    submodules = {}

    out = git.config(l = True, file = ".gitmodules")
    lines = out.splitlines(False)
    for l in lines:
        if not l.startswith("submodule."):
            continue
        full_key, value = l[10:].split("=", 1)
        # Note that name of a submodule may contain dots while dot is
        # also separator in `full_key`.
        for prop in (".url", ".path"):
            if full_key.endswith(prop):
                name = full_key[:-len(prop)]
                submodules.setdefault(name, {})[prop] = value

    # Previous value of submodule URL used when `revert_urls`.
    url_back = None

    for sm, props in submodules.items():
        # If path is absent, it's considered equal to name.
        sm_path = props.get(".path", sm)

        if not repo_path_in_tree(repo, sm_path):
            # The submodule has likely been removed from tree.
            continue

        for cache_dir in cache_dirs:
            sub_cache = join(cache_dir, sm)

            if exists(sub_cache):
                if revert_urls:
                    url_back = git.config(
                        "submodule." + sm + ".url",
                        file = ".gitmodules",
                    )

                # https://stackoverflow.com/a/30675130/7623015
                git.config(
                    "submodule." + sm + ".url",
                    sub_cache,
                    file = ".gitmodules",
                )
                # When initializing submodules of a local clone setting URL in
                # .gitmodules is sufficient to force Git use local cache during
                # "update" command.
                # However, initialization of a worktree (see "git worktree")
                # submodules still uses original URLs. The "sync" command fixes
                # it.
                #
                # Note that Git keeps cache of worktree submodules in a
                # different place (i.e. caches of main work tree submodules
                # are not re-used):
                # .git/worktrees/[worktree name]/modules/[path to submodule]
                git.submodule("sync", sm_path)
                break
        else:
            print("Submodule %s has no cache at %s."
                  " Default URL will be used." % (
                    sm if sm == sm_path else ("%s (%s)" % (sm, sm_path)),
                    ", ".join(map("'%s'".__mod__, cache_dirs))
                )
            )

        git.submodule("update", "--init", sm_path)

        sub_repo = Repo(join(repo.working_tree_dir, sm_path))
        init_submodules_from_cache(sub_repo,
            list(join(cache_dir, sm_path, "modules")
                 for cache_dir in cache_dirs
            ),
            revert_urls = revert_urls
        )

        if url_back is not None:
            git.config(
                "submodule." + sm + ".url",
                url_back,
                file = ".gitmodules"
            )
            url_back = None
            # Updates URL in cache "config" file.
            git.submodule("sync", sm_path)

    if prev_protocol_file_allow:
        if prev_protocol_file_allow != "always":
            git.config("--global", "protocol.file.allow",
                prev_protocol_file_allow
            )
    else:
        git.config("--global", "--unset", "protocol.file.allow")


def git_find_commit(repo, version):
    """ A wrapper for Repo.commit. It also searches the version as
a remote head.
    """
    try:
        return repo.commit(version)
    except BadName:
        # Try to look the version (it's a branch) in remotes.
        for rem in repo.remotes:
            for ref in rem.refs:
                if ref.remote_head == version:
                    return ref.commit

        raise


# Based on: https://stackoverflow.com/a/25961128/7623015
def repo_path_in_tree(repo, path):
    """
@param repo: is a gitPython Repo object
@param path: is the full path to a file/directory from the repository root

Returns `true` if path exists in the repo in current version,
        `false` otherwise.
    """

    # Build up reference to desired repo path
    rsub = repo.head.commit.tree

    for path_element in path.split(sep):
        # If dir on file path is not in repo, neither is file/directory.
        try :
            rsub = rsub[path_element]
        except KeyError:
            return False

    return True
