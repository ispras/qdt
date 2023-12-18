from common import (
    callco,
    iter_submodules_caches,
    fast_repo_clone,
    QRepo,
)

from git import (
    Repo,
)
from os import (
    makedirs,
)
from os.path import (
    abspath,
    dirname,
    exists,
    join,
)
from shutil import (
    rmtree,
)


def main():
    FILE_DIR = dirname(abspath(__file__))
    TEST_ROOT = join(FILE_DIR, "git_worktrees_root")

    # cleanup
    if exists(TEST_ROOT):
        rmtree(TEST_ROOT)

    makedirs(TEST_ROOT)

    submodule0_base = join(TEST_ROOT, "submodule0")

    submodule0 = Repo.init(submodule0_base)
    with open(join(submodule0.working_dir, "file.txt"), "w") as f:
        f.write("v0\n")
    submodule0.index.add("file.txt")
    submodule0_commit0 = submodule0.index.commit(
        message = "initial commit",
    )
    with open(join(submodule0.working_dir, "file.txt"), "w") as f:
        f.write("v1\n")
    submodule0.index.add("file.txt")
    submodule0_commit1 = submodule0.index.commit(
        message = "commit",
    )

    repo_base = join(TEST_ROOT, "repo")
    repo = Repo.init(repo_base)

    print(list(iter_submodules_caches(repo)))

    sm0 = repo.create_submodule(
        name = "submodule0",
        path = "sm0",
        url = submodule0_base,
    )
    # repo.index.add("sm0")
    repo_commit0 = repo.index.commit(
        message = "add submodule with name submodule0 with at path sm0",
    )


    qrepo = QRepo(repo_base)


    worktree0_base = join(TEST_ROOT, "wt0")
    callco(qrepo.co_create_worktree(worktree0_base))

    # worktree from worktree (worktree chain)
    worktree1_base = join(TEST_ROOT, "wt1")
    qworktree0 = QRepo(worktree0_base)

    print(list(iter_submodules_caches(qworktree0.repo)))

    callco(qworktree0.co_create_worktree(worktree1_base))

    worktree1 = Repo(worktree1_base)

    print(list(iter_submodules_caches(worktree1)))

    fast_clone = fast_repo_clone(worktree1)

    print("done") # for a breakpoint


if __name__ == "__main__":
    exit(main() or 0)
