"""
A script for testing of `init_submodules_from_cache` operation.
"""

from common import (
    init_submodules_from_cache
)
from git import (
    Repo
)
from sys import (
    argv
)
from os.path import (
    join
)


if __name__ == "__main__":
    try:
        path = argv[1]
    except IndexError:
        print("Need Git repo path")
        exit(1)

    repo = Repo(path)

    clone_path = path + ".clone"
    repo_clone = repo.clone(clone_path, shared = True)

    init_submodules_from_cache(repo_clone,
        join(repo.working_tree_dir, ".git", "modules"),
        revert_urls = True
    )
