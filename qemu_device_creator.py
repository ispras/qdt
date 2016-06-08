#!/usr/bin/python2

import argparse
import os.path
from _io import open
from qemu import \
    pci_id_db, \
    SysBusDeviceDescription, \
    PCIExpressDeviceDescription, \
    QProject, \
    MachineNode
    

from examples import *

import qemu
from source import Header

def arg_type_directory(string):
    if not os.path.isdir(string):
        raise argparse.ArgumentTypeError(
            "{} is not directory".format(string))
    return string

def main():
    parser = argparse.ArgumentParser(
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
        '--qemu-src', '-q',
        default = '.',
        type=arg_type_directory,
        metavar='path_to_qemu_source_tree',
        )

    parser.add_argument(
        '--gen-header-tree',
        default = None,
        metavar = "header_tree.gv"
        )

    arguments = parser.parse_args()

    qemu.initialize(arguments.qemu_src)

    if not arguments.gen_header_tree == None:
        Header.gen_header_inclusion_dot_file(arguments.gen_header_tree)

    test_vendor = pci_id_db.get_vendor(name = "AMD", vid = "0x1022")
    test_device = pci_id_db.get_device(name = "AMD_LANCE",
            vendor_name = "AMD", did = "0x2000")

    q35_test_init()

    """
    project = QProject(
        descriptions = [
                q35_macine,
                PCIExpressDeviceDescription(
                    name = "Test PCI NIC",
                    directory = "net",
                    vendor = test_vendor,
                    device = test_device,
                    subsys = test_device,
                    subsys_vendor = test_vendor,
                    pci_class = pci_id_db.get_class("NETWORK_ETHERNET"),
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

    project = q35_project

    project.gen_all(arguments.qemu_src)

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