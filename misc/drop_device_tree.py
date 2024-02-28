from common import (
    pythonize,
)
from qemu import (
    load_qvc,
)

from argparse import (
    ArgumentParser,
)
from shutil import (
    copy2,
)


def main():
    ap = ArgumentParser()
    arg = ap.add_argument

    arg("qvc")

    args = ap.parse_args()

    qvc_path = args.qvc
    qvc_path_back = qvc_path + ".back"

    qvc = load_qvc(qvc_path)

    qvc.device_tree = None

    copy2(qvc_path, qvc_path_back)
    pythonize(qvc, qvc_path)


if __name__ == "__main__":
    exit(main() or 0)
