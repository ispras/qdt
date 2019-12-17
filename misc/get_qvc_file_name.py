from argparse import (
    ArgumentParser
)
from sys import (
    path as PYTHONPATH
)
from os.path import (
    abspath,
    dirname
)

from sys import (
    stderr
)
from os import (
    getcwd
)

PYTHONPATH.insert(0, dirname(dirname(abspath(__file__))))

from qemu import (
    gen_qvc_file_name
)


def main():
    stderr.write(getcwd())

    ap = ArgumentParser()
    ap.add_argument("-s", default = "")
    args = ap.parse_args()
    print(gen_qvc_file_name(args.s))


if __name__ == "__main__":
    exit(main() or 0)
