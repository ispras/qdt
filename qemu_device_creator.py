#!/bin/python3

import argparse
import os.path
from _io import open
from qemu import SysBusDeviceType
from source import HeaderFile
import sys

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
        name = "DynamipsMPC860IC",
        out_irq_num = 2,
        mmio_num = 1,
        io_num = 1
        )

    header = q_sysbus_dev_t.generate_header();
    
    header.generate(sys.stdout)
    
if __name__ == '__main__':
    main()