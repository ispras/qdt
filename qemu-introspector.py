from qemu.introspection import (
    q_event_dict,
    q_event_list
)
from argparse import (
    ArgumentTypeError,
    ArgumentParser,
    ArgumentError
)
from re import (
    compile
)
from collections import (
    deque
)
from multiprocessing import (
    Process
)
from os import (
    system
)
from os.path import (
    split,
    join
)
from sys import (
    stderr,
    path as python_path
)

pyrsp_path = join(split(__file__)[0], "pyrsp")
if pyrsp_path not in python_path:
    python_path.insert(0, pyrsp_path)

from pyrsp.targets import (
    AMD64
)

re_qemu_system_x = compile(".*qemu-system-.+$")

class QArgumentParser(ArgumentParser):

    def error(self, *args, **kw):
        stderr.write("Error in argument string. Ensure that `--` is passed"
            " before QEMU and its arguments.\n"
        )
        super(QArgumentParser, self).error(*args, **kw)


def main():
    ap = QArgumentParser(
        description = "QEMU runtime introspection tool"
    )
    ap.add_argument("qarg",
        nargs = "+",
        help = "QEMU executable and arguments to it. Prefix them with `--`."
    )
    args = ap.parse_args()

    # executable
    qemu_cmd_args = args.qarg

    # debug info
    qemu_debug = qemu_cmd_args[0]

    qemu_debug_addr = "localhost:4321"

    qemu_proc = Process(
        target = system,
        # XXX: if there are spaces in arguments this code will not work.
        args = (" ".join(["gdbserver", qemu_debug_addr] + qemu_cmd_args),)
    )

    qemu_proc.start()

    qemu_debugger = AMD64(qemu_debug_addr, verbose = True, host = True)

    qemu_debugger.run()

    qemu_proc.join()


if __name__ == "__main__":
    exit(main())
