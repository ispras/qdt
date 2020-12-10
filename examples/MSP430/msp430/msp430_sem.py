from msp430x import (
    msp430_reg_types,
    name_to_format,
    gen_msp430_instructions,
)

registers = [
    CPURegister("pc", 16),
    CPURegister("regs", 16, *gen_reg_names_range('r', start = 1, end = 16))
]

# Overall instruction syntax information
info = CPUInfo(
    registers = registers,
    name_to_format = name_to_format,
    instructions = gen_msp430_instructions(),
    read_size = 2, # word size of provided encoding definition
    reg_types = msp430_reg_types
)
