#!/usr/bin/python2

import examples

from argparse import (
    ArgumentTypeError,
    ArgumentParser
)
from os.path import isdir
from qemu import get_vp
from qemu import qvd_load_with_cache
from traceback import print_exc

def arg_type_directory(string):
    if not isdir(string):
        raise ArgumentTypeError(
            "{} is not directory".format(string))
    return string

def main():
    parser = ArgumentParser(
        description = '''
The program generates device model stub file inside QEMU source tree and
register it as needed.
        ''',
        fromfile_prefix_chars = '@',
        epilog = '''
Use @file to read arguments from 'file' (one per line) 
        '''
    )

    parser.add_argument(
        '--qemu-build', '-b',
        default = '.',
        type = arg_type_directory,
        metavar = 'path_to_qemu_build',
    )

    parser.add_argument(
        '--gen-header-tree',
        default = None,
        metavar = "header_tree.gv"
    )

    parser.add_argument("--gen-chunk-graphs",
        action = 'store_true',
        help = "also generate Graphviz files with graph of chunks per each "
        "generated source"
    )

    arguments = parser.parse_args()

    try:
        qvd = qvd_load_with_cache(arguments.qemu_build)
    except:
        print("QVD loading failed")
        print_exc()
        return -1

    qvd.use()

    if arguments.gen_header_tree is not None:
        qvd.qvc.stc.gen_header_inclusion_dot_file(arguments.gen_header_tree)

    DefaultProject = getattr(examples,
        get_vp()["QDC default project class name"]
    )
    project = DefaultProject()
    project.gen_all(qvd.src_path,
        with_chunk_graph = arguments.gen_chunk_graphs
    )

    return 0

if __name__ == '__main__':
    main()
