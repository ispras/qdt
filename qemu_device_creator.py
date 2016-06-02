#!/usr/bin/python2

import argparse
import os.path
from _io import open
from qemu import \
    SysBusDeviceType, \
    PCIEDeviceType, \
    pci_id_db, \
    MachineType, \
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

    VERSION_path = os.path.join(arguments.qemu_src, 'VERSION')

    if not os.path.isfile(VERSION_path):
        print("{} does not exists\n".format(VERSION_path))
        return

    VERSION_f = open(VERSION_path)
    qemu_version = VERSION_f.readline().rstrip("\n")
    VERSION_f.close()

    print("Qemu version is {}".format(qemu_version))

    include_path = os.path.join(arguments.qemu_src, 'include')

    qemu.initialize(include_path)

    if not arguments.gen_header_tree == None:
        Header.gen_header_inclusion_dot_file(arguments.gen_header_tree)

    test_vendor = pci_id_db.get_vendor(name = "AMD", vid = "0x1022")
    test_device = pci_id_db.get_device(name = "AMD_LANCE",
            vendor_name = "AMD", did = "0x2000")

    q35_test_init()

    devices = [
        ("i386", q35_macine.gen_machine_type()), 
        ("net", PCIEDeviceType(
            name = "Test PCI NIC",
            directory = "net",
            vendor = test_vendor,
            device = test_device,
            subsys = test_device,
            subsys_vendor = test_vendor,
            pci_class = pci_id_db.get_class("NETWORK_ETHERNET"),
            mem_bar_num = 1,
            msi_messages_num = 2
        )),
        ("intc", SysBusDeviceType(
            name = "Dynamips MPC860 CPCR",
            directory = "intc",
            out_irq_num = 0,
            mmio_num = 1,
            pio_num = 0,
            in_irq_num = 0
        )
        )
    ]

    for device_purpose_class, dev_t in devices:
        device_derectory = device_purpose_class

        full_source_path =  os.path.join(arguments.qemu_src,
            dev_t.source.path)
    
        source_base_name = os.path.basename(full_source_path)
    
        (source_name, source_ext) = os.path.splitext(source_base_name)
    
        obj_base_name = source_name + ".o"
    
        hw_path = os.path.join(arguments.qemu_src, 'hw')
        class_hw_path = os.path.join(hw_path, device_derectory)
        Makefile_objs_class_path = os.path.join(class_hw_path, 'Makefile.objs')
    
        registered_in_makefile = False
        for line in open(Makefile_objs_class_path, "r").readlines():
            if obj_base_name in [s.strip() for s in line.split(" ")]:
                registered_in_makefile = True
                break
    
        if not registered_in_makefile:
            with open(Makefile_objs_class_path, "a") as Makefile_objs:
                Makefile_objs.write(u"obj-y += %s\n" % obj_base_name)
    
        if os.path.isfile(full_source_path):
            os.remove(full_source_path)
    
        source_writer = open(full_source_path, "wb")
        source = dev_t.generate_source()
        source.generate(source_writer)
        source_writer.close()
    
        if "header" in dev_t.__dict__:
            full_header_path = os.path.join(include_path, dev_t.header.path)
            if os.path.isfile(full_header_path):
                os.remove(full_header_path)
    
            header_writer = open(full_header_path, "wb")
            header = dev_t.generate_header()
            header.generate(header_writer)
            header_writer.close()

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