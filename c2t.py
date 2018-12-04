#!/usr/bin/env python
"""QEMU CPU Testing Tool"""

from sys import (
    path,
    stderr
)
from os.path import (
    join,
    split
)
from inspect import (
    getmembers,
    getmro,
    isclass
)
from argparse import (
    ArgumentParser
)

# use custom pyrsp
path.insert(0, join(split(__file__)[0], "pyrsp"))

from pyrsp.rsp import (
    RemoteTarget
)
from pyrsp import (
    targets
)

ARCHMAP = {
    name.lower(): obj for name, obj in getmembers(targets)
        if isclass(obj) and RemoteTarget in getmro(obj)[1:]
}

C2T_ERRMSG_FORMAT = "{prog}:\x1b[31m error:\x1b[0m {msg} {arg}\n"


class C2TArgumentParser(ArgumentParser):
    """ Custom ArgumentParser """

    def __init__(self):
        ArgumentParser.__init__(self,
            description = "CPU Testing Tool",
            epilog = ("supported targets: {targets}".format(
                targets = ', '.join("%s" % arch for arch in ARCHMAP)
            ))
        )

    def error(self, msg, optval = ''):
        self.print_usage(stderr)
        self.exit(2, C2T_ERRMSG_FORMAT.format(
            prog = self.prog,
            msg = msg,
            arg = optval
        ))


def main():
    parser = C2TArgumentParser()
    parser.add_argument("-v", "--verbose",
        action = "store_true",
        help = "increase output verbosity"
    )

    args = parser.parse_args()


if __name__ == "__main__":
    main()
