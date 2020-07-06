__all__ = [
    "CPUInfo"
  , "CPURegister"
  , "gen_reg_names_range"
]

from six import (
    integer_types,
)


class CPURegister(object):
    "Class is used to describe CPUState registers and register groups."

    def __init__(self, name, bitsize, *reg_names):
        """
    :param reg_names:
        if the tuple is not empty then the CPURegister describes a group of
    registers
        """
        self.name = name
        self.bitsize = bitsize
        self.reg_names = reg_names
        if reg_names:
            self._len = len(reg_names)
        else:
            self._len = None

    # XXX: storage_size/occupied_size?
    @property
    def size(self):
        if self.bitsize <= 32:
            return 4
        elif self.bitsize <= 64:
            return 8
        else:
            raise ValueError("Unsupported size %d bits for register %s" % (
                self.bitsize, self.name
            ))

    # XXX: удаление гландов через прямую кишку
    #      count/number/quantity/bank_size (банк регистров - есть такой
    #      термин) И `property` не нужно. Какой смысл защищать от записи только
    #      один атрбут?
    @property
    def len(self):
        return self._len


def gen_reg_names_range(base_name, suffix = "", start = 0, end = 1):
    if type(start) is not type(end):
        raise ValueError("Register names range generating error: range start"
            " and end types differ"
        )
    if isinstance(start, integer_types):
        func = str
    elif isinstance(start, str) and len(start) == 1 and len(end) == 1:
        func = chr
        start = ord(start)
        end = ord(end)
    else:
        raise ValueError("Register names range generating error: only integer"
            " or one char ranges are allowed"
        )
    return [base_name + func(i) + suffix for i in range(start, end)]


class CPUInfo(object):
    "This class store CPU info which editing is not supported by the GUI."

    def __init__(self,
        registers = (),
        pc_register = "pc",
        name_to_format = {},
        instructions = (),
        read_size = 1,
        reg_types = (lambda : None)
    ):
        """
    :param registers:
        tuple of `CPURegister`s used in CPU

    :param pc_register:
        the name of one of the registers specified above that will be
        considered a program counter

    :param name_to_format:
        dictionary which describes operand formatting rules for disassembler

    :param instructions:
        tuple of `Instruction`s available in CPU

    :param read_size:
        number of bytes of instruction to be read at one time
        (support 1, 2, 4 or 8 bytes)

    :param reg_types:
        callable object which must register types that can be used in several
        instruction semantics
        """

        self.registers = list(registers)
        self.pc_register = pc_register
        self.name_to_format = dict(name_to_format)
        self.instructions = list(instructions)
        self.read_size = read_size
        self.reg_types = reg_types
