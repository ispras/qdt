__all__ = [
    "CPUEnvField"
  , "CPUInfo"
  , "CPURegister"
  , "gen_reg_names_range"
]

from ..qom_type_state_field import (
    QOMTypeStateField,
)

from six import (
    integer_types,
)


class CPURegister(object):
    "Class is used to describe CPUState registers and register groups."

    def __init__(self, name, bitsize, *reg_names, **kw):
        """
    :param reg_names:
        if the tuple is not empty then the CPURegister describes a group of
    registers
    :param gdb:
        **kw-only. if this register is accessible to gdb. Default: `True`.
        """
        if bitsize > 64:
            raise ValueError("Unsupported size %d bits for register %s" % (
                bitsize, name
            ))

        self.name = name
        self.raw_bitsize = bitsize
        # Note, possible values 32 or 64 bits
        self.field_bitsize = (bitsize + 31) & ~31
        self.reg_names = reg_names
        self.bank_size = len(reg_names) if reg_names else None
        self.gdb = kw.get("gdb", True)


class CPUEnvField(QOMTypeStateField):
    """ Note that, not all of the inherited attributes are applicable.
E.g. *property* settings are ignored.
    """

    def __var_base__(self):
        return "env_fld_" + self.name


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


def no_reg_types(source):
    pass

class CPUInfo(object):
    "This class store CPU info which editing is not supported by the GUI."

    def __init__(self,
        registers = (),
        pc_register = "pc",
        name_to_format = {},
        instructions = (),
        read_size = 1,
        reg_types = no_reg_types,
        reg_disas_types = no_reg_types,
        name_shortener = (lambda args, comment : None),
        env_extra_fields = (),
    ):
        """
    :param registers:
        tuple of `CPURegister`s used in CPU

    :param pc_register:
        the name (or tuple with name and index) of one of the registers
        specified above that will be considered a program counter

    :param name_to_format:
        dictionary which describes instructions operands formatting rules for
        disassembler

        Keys must match (correspond) to place names inside
            Instruction.disas_format.
        Values are tuples of (format_specifier, operand_value_adapter).

        A place is defined as comma separated <names, of, operands> inside
            <angle parenthesis>.
        One <name> is enough for simple operand formatting.

        `name` can match argument of `print_insn_*`, the top level function of
        encoding parser.
        Then `operand_value_adapter` is given that argument, among with
        instruction operands.

        format_specifier is either None or a (sub-)string, a part of format
        string of printf-like Qemu printing function (ex.: "%s").

        operand_value_adapter can be...
        - None, operand value is used as is.
        - A string, name of function boilerplate to be generated.
          A developer is expected to write its body in C.
        - A function returning an iterable or a generator (or `yield`s
          by self) of `source.function.tree` nodes representing
          pre-generated body of the boilerplate function.

        If format_specifier is None:
            operand_value_adapter is given:
            - Qemu disassembly printing function (pointer to function),
            - a stream pointer
              (the printing function first opaque argument),
            - values of operands listed in key in the same order.

            operand_value_adapter is expected to call the printing function
            to output corresponding part of disassembly

            The printing function can be called multiple times.
        else: # if format_specifier is a format string
            operand_value_adapter is given:
            - values of operands listed in key in the same order.

            operand_value_adapter is expected to return a value corresponding
            to the format_specifier.

    :param instructions:
        tuple of `Instruction`s

    :param read_size:
        number of bytes of code to be read at one time during instruction
        identification (support 1, 2, 4 or 8 bytes)

    :param reg_types:
        callable object which gets source `translate.inc.c` and must register
        types and functions that can be used in several instruction semantics

    :param reg_disas_types:
        callable object which gets disas source and must register types and
        functions that can be used in several instruction prints

    :param name_shortener:
        callable object that is may rename `args` (corresponding to the
        `Instruction` operands) of semantics boilerplate `Function` from
        generated `translate.inc.i3s.c` file (`comment` can be used to specify
        instruction in user notifications)

    :param env_extra_fields:
        an iterable of `CPUEnvField`s to be added to `CPU*State`
        """

        self.registers = list(registers)
        self.pc_register = pc_register
        self.name_to_format = dict(name_to_format)
        self.instructions = list(instructions)
        self.read_size = read_size
        self.reg_types = reg_types
        self.reg_disas_types = reg_disas_types
        self.name_shortener = name_shortener
        self.env_extra_fields = env_extra_fields
