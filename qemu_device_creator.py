#!/usr/bin/python2

import examples

from argparse import \
    ArgumentTypeError, \
    ArgumentParser

from os.path import \
    isdir

from qemu import \
    get_vp, \
    PCIId

from qemu import \
    qvd_load_with_cache

def arg_type_directory(string):
    if not isdir(string):
        raise ArgumentTypeError(
            "{} is not directory".format(string))
    return string

def main():
    parser = ArgumentParser(
        description='''
The program generates device model stub file inside QEMU source tree and
register it as needed.
        ''',
        fromfile_prefix_chars='@',
        epilog='''
Use @file to read arguments from 'file' (one per line) 
        '''
        )

    parser.add_argument(
        '--qemu-build', '-b',
        default = '.',
        type=arg_type_directory,
        metavar='path_to_qemu_build',
        )

    parser.add_argument(
        '--gen-header-tree',
        default = None,
        metavar = "header_tree.gv"
        )

    parser.add_argument("--gen-chunk-graphs",
        action='store_true',
        help = "also generate Graphviz files with graph of chunks per each "
        "generated source"
    )

    arguments = parser.parse_args()

    try:
        qvd = qvd_load_with_cache(arguments.qemu_build)
    except Exception as e:
        print("QVD load filed: " + str(e) + "\n")
        return -1

    qvd.use()

    if not arguments.gen_header_tree == None:
        qvd.qvc.stc.gen_header_inclusion_dot_file(arguments.gen_header_tree)

    test_device = PCIId.db.get_device(name = "AMD_LANCE",
            vendor_name = "AMD", did = "0x2000")

    """
    project = QProject(
        descriptions = [
                q35_macine,
                PCIExpressDeviceDescription(
                    name = "Test PCI NIC",
                    directory = "net",
                    vendor = "AMD",
                    device = test_device,
                    subsys = test_device,
                    subsys_vendor = "AMD",
                    pci_class = "NETWORK_ETHERNET",
                    mem_bar_num = 1,
                    msi_messages_num = 2
                ),
                SysBusDeviceDescription(
                    name = "Dynamips MPC860 CPCR",
                    directory = "intc",
                    out_irq_num = 0,
                    mmio_num = 1,
                    pio_num = 0,
                    in_irq_num = 0
                )
            ] 
        )
    """

    DefaultProject = getattr(examples,
        get_vp()["QDC default project class name"]
    )
    project = DefaultProject()
    project.gen_all(qvd.src_path,
        with_chunk_graph = arguments.gen_chunk_graphs
    )

    '''
    from pycparser import c_generator, c_ast
    from pycparser.c_ast import FuncDef, ParamList, PtrDecl, TypeDecl,\
        IdentifierType, FuncDecl, FileAST, Constant

    type_void = TypeDecl("opaque", [], IdentifierType(["void"]))
    type_hwaddr = TypeDecl("offset", [], IdentifierType(["hwaddr"]))
    type_unsigned = TypeDecl("size", [], IdentifierType(["unsigned"]))
    type_void_ptr = PtrDecl([], type_void)
    type_uint64_t = TypeDecl("mmio_write", [], IdentifierType(["uint64_t"]))

    f_type_args = ParamList([
        c_ast.Decl(None, [], [], [], type_void_ptr, None, None),
        c_ast.Decl(None, [], [], [], type_hwaddr, None, None),
        c_ast.Decl(None, [], [], [], type_unsigned, None, None)
        ])
    f_type_ret = type_uint64_t
    f_type_decl = FuncDecl(f_type_args, f_type_ret)
    f_decl = c_ast.Decl(None, [], [], [], f_type_decl, None, None)

    f_body = c_ast.Compound([
        c_ast.Return(Constant(None, "0"))
        ])

    mmio_w_f = FuncDef(f_decl, [], f_body)

    ast = FileAST([mmio_w_f])

    generator = c_generator.CGenerator()
    print(generator.visit(ast))
    '''

if __name__ == '__main__':
    main()
