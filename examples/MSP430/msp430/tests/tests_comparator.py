#!/usr/bin/python

from glob import (
    glob
)
from os.path import (
    abspath,
    isdir,
    join,
    basename,
    splitext
)
from difflib import (
    unified_diff
)
from os import (
    getcwd
)

def main():
    directory = getcwd()
    for f in glob(join(directory, "*.s")):
        test = splitext(basename(f))[0]

        with open(join(directory, test + ".hw.log"), "r") as f:
            hw_log = f.readlines()

        with open(join(directory, test + ".qemu.log"), "r") as f:
            qemu_log = f.readlines()

        if hw_log == qemu_log:
            print("TEST %s OK" % test)
        else:
            print("TEST %s DIFFER:" % test)
            print("".join(unified_diff(hw_log, qemu_log)))

main()
