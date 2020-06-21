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

    @property
    def size(self):
        if self.bitsize <= 32:
            return 4
        elif self.bitsize <= 64:
            return 8
        else:
            # TODO: output wrong size too
            raise ValueError("Wrong register size: " + self.name)

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
        # TODO: is `[0]` really needed for `str`?
        start = ord(start[0])
        end = ord(end[0])
    else:
        raise ValueError("Register names range generating error: only integer"
            " or one char ranges are allowed"
        )
    return [base_name + func(i) + suffix for i in range(start, end)]


class CPUInfo(object):
    # XXX: ... editing is not supported by the GUI.
    "This class store CPU info which editing does not support by the GUI."

    def __init__(self,
        registers = None,
        pc_register = "pc",
        name_to_format = None,
        instructions = None,
        read_size = 1,
        reg_types = None
    ):
        """
    :param registers:
        list of `CPURegister`s used in CPU

    :param pc_register:
        the name of one of the registers specified above that will be
        considered a program counter

    :param name_to_format:
        dictionary which describes operand formatting rules for disassembler

    :param instructions:
        list of `Instruction`s available in CPU

    :param read_size:
        number of bytes of instruction to be read at one time
        (support 1, 2, 4 or 8 bytes)

    :param reg_types:
        callable object which must register types that can be used in several
    instruction semantics
        """

        # TODO: can we use empty tuples in defaults for iterables?
        # TODO: can we copy iterables (e.g.by `list(...)`) to prevent outer
        #       modification?
        self.registers = [] if registers is None else registers
        self.pc_register = pc_register
        self.name_to_format = {} if name_to_format is None else name_to_format
        self.instructions = [] if instructions is None else instructions
        self.read_size = read_size
        # TODO: the lambda can be default value
        self.reg_types = (lambda : None) if reg_types is None else reg_types
