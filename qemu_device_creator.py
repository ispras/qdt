#!/usr/bin/python2

import examples

from argparse import (
    ArgumentTypeError,
    ArgumentParser
)
from os.path import (
    isdir
)
from qemu import (
    qvd_load_with_cache
)
from common import (
    execfile
)
from traceback import (
    print_exc
)
import qdt

def arg_type_directory(string):
    if not isdir(string):
        raise ArgumentTypeError(string + " is not directory")
    return string

def main():
    parser = ArgumentParser(
        description = "QEMU Project Generator\n"
        "The tool generates source files inside QEMU source tree according to"
        "settings read from project script."
    )

    parser.add_argument(
        "--qemu-build", "-b",
        default = ".",
        type = arg_type_directory,
        metavar = "/path/to/qemu/build/directory",
        help = "Override QEMU build path of the project."
    )

    parser.add_argument(
        "--gen-header-tree",
        default = None,
        metavar = "header_tree.gv",
        help = "Output QEMU header inclusion graph in Graphviz format."
    )

    parser.add_argument(
        "--gen-chunk-graphs",
        action = "store_true",
        help = "Generate Graphviz files with graph of chunks per each "
        "generated source."
    )

    parser.add_argument(
        "script",
        help = "A Python script containing definition of a project to generate."
    )

    arguments = parser.parse_args()

    script = arguments.script

    loaded = {}
    try:
        execfile(script, qdt.__dict__, loaded)
    except:
        print("Cannot load configuration from '%s'" % script)
        print_exc()
        return -1

    for v in loaded.values():
        if isinstance(v, qdt.QProject):
            project = v
            break
    else:
        print("Script '%s' does not define a project to generate." % script)
        return -1

    try:
        qemu_build_path = project.build_path
    except:
        qemu_build_path = arguments.qemu_build
    else:
        if not qemu_build_path:
            qemu_build_path = arguments.qemu_build

    try:
        qvd = qvd_load_with_cache(qemu_build_path)
    except:
        print("QVD loading failed")
        print_exc()
        return -1

    qvd.use()

    if arguments.gen_header_tree is not None:
        qvd.qvc.stc.gen_header_inclusion_dot_file(arguments.gen_header_tree)

    project.gen_all(qvd.src_path,
        with_chunk_graph = arguments.gen_chunk_graphs
    )

    return 0

if __name__ == '__main__':
    exit(main())
