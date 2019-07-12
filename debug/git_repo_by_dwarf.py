__all__ = [
    "git_repo_by_dwarf"
]

from os.path import (
    abspath,
    dirname
)
from six import (
    PY3
)
from git import (
    Repo
)


def git_repo_by_dwarf(dwarf_info, limit = None):
    """ Given a DWARF Info (pyelftools), the helper searches for a related Git
repository. Then it returns `Repo` object.

:param limit:
    is maximum amount of paths those may be probed
    """

    repo = None
    citer = dwarf_info.iter_CUs()
    checked = set()

    while repo is None and (limit is None or len(checked) < limit):
        try:
            cu = next(citer)
        except StopIteration: # no more CUs
            break

        src_file = cu.get_top_DIE().attributes["DW_AT_name"].value
        if PY3:
            # TODO: Is DWARF file name encoding always utf-8?
            src_file = src_file.decode("utf-8")
        src_path = abspath(dirname(src_file))

        # Start from directory of the file and go towards file system root
        # until a Git repository is found
        while src_path:
            if src_path in checked:
                break
            checked.add(src_path)

            try:
                repo = Repo(src_path)
                break
            except:
                parent = dirname(src_path)
                if len(parent) == len(src_path):
                    # Note, `dirname` of file system root is that root
                    break
                src_path = parent

    if repo is None:
        raise ValueError("Can't find a source tree under Git.")

    return repo
