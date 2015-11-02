#!/bin/python3

import argparse
import os.path
from _io import open
from qemu import SysBusDeviceType
from source import HeaderFile
import sys

from pycparser import c_generator, c_ast
from pycparser.c_ast import FuncDef, ParamList, PtrDecl, TypeDecl,\
    IdentifierType, FuncDecl, FileAST, Constant

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
    
    
    arguments = parser.parse_args()
    
    VERSION_path = os.path.join(arguments.qemu_src, 'VERSION')
    
    if not os.path.isfile(VERSION_path):
        print("{} does not exists\n".format(VERSION_path))
        return
    
    VERSION_f = open(VERSION_path)
    qemu_version = VERSION_f.readline()
    VERSION_f.close()
    
    print("Qemu version is {}\n".format(qemu_version))
    
    q_sysbus_dev_t = SysBusDeviceType(
        name = "Dynamips MPC860 IC",
        out_irq_num = 2,
        mmio_num = 1,
        pio_num = 1,
        in_irq_num = 1
        )

    header = q_sysbus_dev_t.generate_header()
    
    header.generate(sys.stdout)
    
    source = q_sysbus_dev_t.generate_source()
    
    source.generate(sys.stdout)
    
    '''
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