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
        if bitsize > 64:
            raise ValueError("Unsupported size %d bits for register %s" % (
                bitsize, name
            ))

        self.name = name
        # Note, possible values 32 or 64 bits
        self.field_bitsize = (bitsize + 31) & ~31
        self.reg_names = reg_names
        self.bank_size = len(reg_names) if reg_names else None


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
    return [(base_name + func(i) + suffix) for i in range(start, end)]


class CPUInfo(object):
    "This class store CPU info which editing is not supported by the GUI."

    def __init__(self,
        registers = (),
        pc_register = "pc",
        name_to_format = {},
        instructions = (),
        read_size = 1,
        reg_types = (lambda : None),
        name_shortener = (lambda args, comment : None)
    ):
        """
    :param registers:
        tuple of `CPURegister`s used in CPU

    :param pc_register:
        the name of one of the registers specified above that will be
        considered a program counter

    :param name_to_format:
        dictionary which describes instructions operands formatting rules for
        disassembler

    :param instructions:
        tuple of `Instruction`s

    :param read_size:
        number of bytes of code to be read at one time during instruction
        identification (support 1, 2, 4 or 8 bytes)

    :param reg_types:
        callable object which must register types that can be used in several
        instruction semantics

    :param name_shortener:
        callable object that is may rename `args` (corresponding to the
        `Instruction` operands) of semantics boilerplate `Function` from
        generated `translate.inc.i3s.c` file (`comment` can be used to specify
        instruction in user notifications)

        """

        self.registers = list(registers)
        self.pc_register = pc_register
        self.name_to_format = dict(name_to_format)
        self.instructions = list(instructions)
        self.read_size = read_size
        self.reg_types = reg_types
        self.name_shortener = name_shortener
