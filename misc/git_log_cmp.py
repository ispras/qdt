from common import (
    makedirs,
)

from argparse import (
    ArgumentParser,
)
from git import (
    Repo,
)
from os import (
    getcwd,
    remove,
)
from os.path import (
    dirname,
    isfile,
    sep,
)
from re import (
    compile,
)
from subprocess import (
    run,
)


re_commit = compile(r"^commit [0-9a-f]{40}$")
re_commit_match = re_commit.match
is_commit_line = lambda l: bool(re_commit_match(l))


def main():
    ap = ArgumentParser(
        description = """\
Helper to compare `git log` (commit summary) of different revisions as text.
"""     ,
    )
    arg = ap.add_argument

    arg("rev_ids",
        action = "append",
    )
    arg("--worktree", "-w",
        default = getcwd(),
        nargs = 1,
    )
    arg("--prefix", "-p",
        default = getcwd() + sep + ".",
        nargs = 1,
        help = "prefix (!= directory) for working files names",
    )
    arg("--cmptool", "-t",
        default = [],
        action = "append",
        help = "text log comparison tool; use several times to pass args",
    )
    arg("--no-cleanup", "-C",
        action = "store_true",
        help = "don't remove generated log files"
    )

    args = ap.parse_args()

    rev_ids = list(args.rev_ids)
    if len(rev_ids) == 1:
        rev_ids.append("HEAD")

    if len(rev_ids) != 2:
        raise ValueError("1 or 2 `rev_id` are required")

    cmptool = args.cmptool
    if not cmptool:
        cmptool.append("meld")

    r = Repo(args.worktree)
    git = r.git

    base = git.merge_base(*rev_ids)

    prefix = args.prefix

    prefix_dir = dirname(prefix)
    makedirs(prefix_dir, exist_ok = True)

    glogs = []
    for rev_id in rev_ids:
        rev_range = base + ".." + rev_id
        glog = GitLog(
            data = git.log(rev_range),
            file_name = prefix + rev_range + ".log",
        )
        glogs.append(glog)

    for glog in glogs:
        glog.normalize()
        glog.flush()

    try:
        run(cmptool + list(glog.file_name for glog in glogs))
    finally:
        if not args.no_cleanup:
            for glog in glogs:
                glog.cleanup()


class GitLog(object):

    __slots__ = (
        "data",
        "file_name",
    )

    def __init__(self, **kw):
        for nv in kw.items():
            setattr(self, *nv)

    def normalize(self):
        lines = []

        for l in self.data.splitlines(True):
            # Commit ids are definetly differ.
            # Drop them to don't junk diff.
            if is_commit_line(l):
                continue
            lines.append(l)

        self.data = "".join(lines)

    def flush(self):
        with open(self.file_name, "w") as f:
            f.write(self.data)

    def cleanup(self):
        if isfile(self.file_name):
            remove(self.file_name)


if __name__ == "__main__":
    exit(main() or 0)
