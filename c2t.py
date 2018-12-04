#!/usr/bin/env python
"""QEMU CPU Testing Tool"""

from sys import (
    path,
    stderr
)
from os import (
    listdir
)
from os.path import (
    join,
    split,
    dirname,
    exists
)
from inspect import (
    getmembers,
    getmro,
    isclass
)
from argparse import (
    ArgumentParser
)
from re import (
    compile
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

C2T_DIR = dirname(__file__) or '.'
C2T_CONFIGS_DIR = join(C2T_DIR, "c2t", "configs")
C2T_TEST_DIR = join(C2T_DIR, "c2t", "tests")


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


def get_tests(regexp):
    r = compile("%s[.]c$" % regexp)
    return list(filter(r.match, listdir(C2T_TEST_DIR)))


def main():
    parser = C2TArgumentParser()
    parser.add_argument("-c", "--config",
        type = str,
        dest = "config",
        help = "configuration file for %s" % parser.prog
    )
    parser.add_argument("-t", "--test",
        type = str,
        dest="regexp",
        help = ("regular expression that defines a test set"
             " (tests are located in %s)"
        ) % C2T_TEST_DIR
    )
    parser.add_argument("-v", "--verbose",
        action = "store_true",
        help = "increase output verbosity"
    )

    args = parser.parse_args()

    if not args.config or not args.regexp:
        parser.error("requires more input arguments to run")

    config = join(C2T_CONFIGS_DIR, "%s.py" % args.config)
    if not exists(config):
        config = join(C2T_DIR, "%s.py" % args.config)
        if not exists(config):
            parser.error("configuration file doesn't exist:",
                optval = args.config
            )

    tests = get_tests(args.regexp)
    if not tests:
        parser.error("no matches in %s with:" % C2T_TEST_DIR,
            optval = args.regexp
        )


if __name__ == "__main__":
    main()
