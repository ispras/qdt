from qemu import (
    qvd_load_with_cache
)
from sys import (
    argv
)
from  argparse import (
    ArgumentParser
)
from arch_parser import (
    Arch
)

def parse_endian(string):
    res = string.lower()
    if res not in ['big', 'little']:
        raise Exception('Wrong endianness option: {}'.format(string))
    return res == 'big'

def main():
    cmd_args = argv[1:]

    argparser = ArgumentParser()
    argparser.add_argument(
        'arch_name',
        help = 'Target architecture name'
    )
    argparser.add_argument(
        'qemu_folder',
        help = 'QEMU root folder'
    )
    argparser.add_argument(
        '-e',
        '--arch-endian',
        help = 'Target ARCH endianness'
    )
    argparser.add_argument(
        '-v',
        '--verbose',
        action = 'store_true',
        help = 'Produce an additional output when '
        'creating parsing tree'
    )
    argparser.add_argument(
        '-d',
        action = 'store_true',
        help = 'Generate ARCH decoder tests'
    )
    argparser.add_argument(
        '-y',
        '--overwrite',
        help = 'Overwrite existing files without a prompt',
        action = 'store_true'
    )
    argparser.add_argument(
        '--gen-chunk-graphs',
        action = 'store_true',
        help = 'Generate Graphviz files with graph of chunks per each '
        'generated source.'
    )
    argparser.add_argument(
        '--gen-debug-comments',
        action = 'store_true',
        help = 'Generate source files with debug comments.'
    )

    argparser.add_argument(
        "--gen-header-tree",
        default = None,
        metavar = "header_tree.gv",
        help = "Output QEMU header inclusion graph in Graphviz format."
    )

    args = vars(argparser.parse_args(cmd_args))

    if args['arch_endian'] is not None:
        arch_big_endian = parse_endian(args['arch_endian'])
    else:
        arch_big_endian = False

    qvd = qvd_load_with_cache(args['qemu_folder'])

    if args['gen_header_tree'] is not None:
        qvd.qvc.stc.gen_header_inclusion_dot_file(args['gen_header_tree'])

    arch = Arch(
        args['arch_name'],
        qvd.src_path,
        arch_big_endian,
        args['verbose'],
        args['d'],
        args['overwrite'],
        args['gen_chunk_graphs'],
        args['gen_debug_comments']
    )

    if arch.fill() is None:
        print('Failed to fill ISA parsing tree')
        return 1

    arch.gen_all()
    return 0

if __name__ == '__main__':
    main()
