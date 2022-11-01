#!/usr/bin/env /usr/bin/python3

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

re_index = compile(r"^index [0-9a-f]{9}..[0-9a-f]{9} \d{6}$")
re_index_match = re_index.match
is_index_line = lambda l: bool(re_index_match(l))


def main():
    ap = ArgumentParser(
        description = """\
Helper to compare `git log` (commit summary) of different revisions as text.
"""     ,
    )
    arg = ap.add_argument

    arg("rev_id",
        nargs = "+",
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
        help = "don't remove generated log files",
    )
    arg("--showpatch", "-s",
        action = "store_true",
        help = "show patch for every commit",
    )

    args = ap.parse_args()

    rev_ids = list(args.rev_id[0])
    if len(rev_ids) == 1:
        rev_ids.append("HEAD")

    if len(rev_ids) != 2:
        ap.error("1 or 2 `rev_id` are required")
        assert 0, "this line must not be reached"

    cmptool = args.cmptool
    if not cmptool:
        cmptool.append("meld")

    r = Repo(args.worktree)
    git = r.git

    base = git.merge_base(*rev_ids)

    prefix = args.prefix

    prefix_dir = dirname(prefix)
    makedirs(prefix_dir, exist_ok = True)

    showpatch = args.showpatch

    glogs = []
    for rev_id in rev_ids:
        rev_range = base + ".." + rev_id
        if showpatch:
            log_args = (rev_range, "-p")
        else:
            log_args = (rev_range,)
        glog = GitLog(
            data = git.log(*log_args),
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
            # Commit ids are definitely differ.
            # Drop them to don't junk diff.
            if is_commit_line(l):
                continue
            if is_index_line(l):
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
