#!/usr/bin/python

from argparse import (
    ArgumentTypeError,
    ArgumentParser,
)
from os.path import (
    abspath,
    isdir,
    join,
    basename,
    splitext
)
from glob import (
    glob
)
from re import (
    compile
)
from collections import (
    OrderedDict
)


# msp430x instruction set description

# addressing modes


class RegisterMode:
    pass


class RegisterModeR0(RegisterMode):
    pass


class RegisterModeR1(RegisterMode):
    pass


class RegisterModeR2(RegisterMode):
    pass


# Note: interpreted as 0 constant if it is src ("R3, As = 00", page 193)
class RegisterModeR3(RegisterMode):
    pass


# R4-R15 registers
class RegisterModeRn(RegisterMode):
    pass


class IndexedMode:
    pass


# X(PC), X(R0) Indexed mode is used for coding
class SymbolicMode:
    pass


# X(SR), X(R2) Indexed mode is used for coding
class AbsoluteMode:
    pass


class IndirectRegisterMode:
    pass


class IndirectAutoincrementMode:
    pass


# impossible, used for coding ImmediateMode
#class IndirectAutoincrementModeR0(IndirectAutoincrementMode):
#    pass


class IndirectAutoincrementModeR1(IndirectAutoincrementMode):
    pass


class IndirectAutoincrementModeR2(IndirectAutoincrementMode):
    pass


class IndirectAutoincrementModeR3(IndirectAutoincrementMode):
    pass


# R4-R15 registers
class IndirectAutoincrementModeRn(IndirectAutoincrementMode):
    pass


# @PC+ Indirect Autoincrement mode is used for coding
class ImmediateMode:
    pass


ModeToStr = {
    RegisterModeR0: "PC",
    RegisterModeR1: "SP",
    RegisterModeR2: "SR",
    RegisterModeR3: "R3",
    RegisterModeRn: "Rn",
    IndexedMode: "X(Rn)",
    SymbolicMode: "ADDR",
    AbsoluteMode: "&ADDR",
    IndirectRegisterMode: "@Rn",
    IndirectAutoincrementModeR1: "@SP+",
    IndirectAutoincrementModeR2: "@SR+",
    IndirectAutoincrementModeR3: "@R3+",
    IndirectAutoincrementModeRn: "@Rn+",
    ImmediateMode: "#N"
}

SrcAddrMode = [
    #RegisterMode, # replaced by RegisterModeR0..RegisterModeRn modes
    RegisterModeR0,
    RegisterModeR1,
    RegisterModeR2,
    RegisterModeR3,
    RegisterModeRn,

    IndexedMode,
    SymbolicMode,
    AbsoluteMode,
    IndirectRegisterMode,

    #IndirectAutoincrementMode, # replaced by IndirectAutoincrementModeR1..IndirectAutoincrementModeRn modes
    IndirectAutoincrementModeR1,
    IndirectAutoincrementModeR2,
    IndirectAutoincrementModeR3,
    IndirectAutoincrementModeRn,

    ImmediateMode
]

DstAddrMode = [
    RegisterModeR0,
    RegisterModeR1,
    RegisterModeR2,
    RegisterModeR3,
    RegisterModeRn,
    IndexedMode,
    SymbolicMode,
    AbsoluteMode
]


def parse_arg_mode(arg, is_src = True):
    # see page 193 (Constant Generator Registers)
    if is_src and arg == "#0":
        return RegisterModeR3

    if arg[0] == "#":
        return ImmediateMode

    if arg[0] == "@":
        if arg[-1] == "+":
            return IndirectAutoincrementMode
        else:
            return IndirectRegisterMode

    # TODO: no real example in IR, may parse wrong
    if arg[-4:] == "(R0)": # TODO: maybe (PC)
        return SymbolicMode
    if arg[-4:] == "(R2)": # TODO: maybe (SR)
        return AbsoluteMode

    if arg[-1] == ")":
        return IndexedMode

    if arg == "R0":
        return RegisterModeR0
    if arg == "R1":
        return RegisterModeR1
    if arg == "R2":
        return RegisterModeR2
    if arg == "R3":
        return RegisterModeR3
    if arg[0] == "R":
        return RegisterModeRn

    raise RuntimeError("Mode not recognized: %s" % arg)

instructions = OrderedDict()
mnemonic_aliases = {}
emulated_instructions = {}

def FI(name):
    for extension in ["", "X"]:
        sizes = ([".A"] if extension else []) + [".W", ".B"]
        FI_sizes(name + extension, sizes)
        mnemonic_aliases[name + extension] = name + extension + ".W"

def FI_sizes(name, sizes):
    for size in sizes:
        for arg1Type in SrcAddrMode:
            for arg2Type in DstAddrMode:
                instructions[(name + size, arg1Type, arg2Type)] = []

def FII(name, AddrMode = DstAddrMode, flags = [".W", ".B"]):
    for flag in flags:
        for arg1Type in AddrMode:
            instructions[(name + flag, arg1Type)] = []
    mnemonic_aliases[name] = name + ".W"

def FII_RETI():
    instructions[("RETI",)] = []

def J(name):
    # TODO: register jump instructions
    pass

def A(name):
    # TODO: register address instructions
    pass

# MSP430 Double-Operand (Format I) Instructions
# &
# MSP430X Extended Double-Operand (Format I) Instructions
for i in [
    "MOV",
    "ADD",
    "ADDC",
    "SUB",
    "SUBC",
    "CMP",
    "DADD",
    "BIT",
    "BIC",
    "BIS",
    "XOR",
    "AND"
]:
    FI(i)

# MSP430 Single-Operand (Format II) Instructions
for i in [
    "RRC",
    "RRA",
    ("PUSH", SrcAddrMode), # arg is src (not dst)
    ("SWPB", DstAddrMode, [".W"]), # only W flag
    "CALL",
    #"RETI" # no explicit dst
    ("SXT", DstAddrMode, [".W"]) # only W flag
]:
    if type(i) is tuple:
        FII(*i)
    else:
        FII(i)

FII_RETI()

# MSP430 Jump Instructions
for i in [
    "JEQ",
    "JNE",
    "JC",
    "JNC",
    "JN",
    "JGE",
    "JL",
    "JMP"
]:
    J(i)
mnemonic_aliases["JZ"] = "JEQ"
mnemonic_aliases["JNZ"] = "JNE"

# MSP430 Emulated Instructions
emulated_instructions[("NOP",)] = ("MOV.W", RegisterModeR3, RegisterModeR3)
emulated_instructions[("RET",)] = ("MOV.W", IndirectAutoincrementModeR1, RegisterModeR0)
# TODO: add them all (page 215)

# MSP430X Extended Single-Operand (Format II) Instructions
# TODO: add

# MSP430X Address Instructions
for i in [
    "ADDA",
    "MOVA",
    "CMPA",
    "SUBA"
]:
    A(i)

# MSP430X Extended Emulated Instructions
# TODO: add

def arg_type_directory(string):
    if not isdir(string):
        raise ArgumentTypeError(string + " is not directory")
    return string

def main():
    parser = ArgumentParser(description = "MSP430x tests coverage")

    parser.add_argument(
        "irdir",
        type = arg_type_directory,
        metavar = "/path/to/c2t/tests/ir/directory",
        help = "Path to directory with disas files"
    )
    parser.add_argument("-o", "--output",
        metavar = "coverage.csv",
        default = "ir_disas_table.csv",
        help = "Name of output verbose coverage table",
    )
    parser.add_argument("-s", "--summary",
        metavar = "summary.csv",
        help = "Name of coverage summary table (name & size only)"
    )

    arguments = parser.parse_args()

    tests = []
    # XXX: hard-coded 2-byte address and first 2-byte instruction machine word
    line_with_instr = compile("^ +\d+"
        " [0-9A-F][0-9A-F][0-9A-F][0-9A-F]"
        " [0-9A-F][0-9A-F][0-9A-F][0-9A-F]"
        ".+\t\t(.+)$"
    )

    processed_instructions_count = 0
    not_found_instructions_count = 0

    for irfile in glob(join(abspath(arguments.irdir), "*.disas")):
        test = splitext(basename(irfile))[0]
        tests.append(test)
        with open(irfile, "r") as f:
            lines = f.readlines()

        for line in lines:
            mi = line_with_instr.match(line)
            if not mi:
                continue

            instr_line = mi.group(1).split("\t")
            instr_mnem = instr_line[0]
            instr_mnem = mnemonic_aliases.get(instr_mnem, instr_mnem)
            if len(instr_line) == 2:
                instr_args = instr_line[1].split(", ")
                instr_args_count = len(instr_args)
                if instr_args_count == 1:
                    # use src parsing for PUSH instruction
                    flag = instr_mnem in ["PUSH.B", "PUSH.W"]
                    instr = (instr_mnem, parse_arg_mode(instr_args[0], flag))
                elif instr_args_count == 2:
                    src_mode = parse_arg_mode(instr_args[0])
                    dst_mode = parse_arg_mode(instr_args[1], False)
                    if dst_mode == IndirectRegisterMode:
                        # page 209: The substitute for the destination operand is 0(Rdst)
                        dst_mode = IndexedMode
                    instr = (instr_mnem, src_mode, dst_mode)
                else:
                    print('"%s" from "%s" ignored (wrong count of'
                        " arguments)" % (" ".join(instr_line), test)
                    )
                    continue
            else:
                instr = (instr_mnem,)

            instr = emulated_instructions.get(instr, instr)

            try:
                instructions[instr].append(test)
                processed_instructions_count += 1
            except KeyError:
                print('NOT FOUND: "%s" from "%s"' % (
                    " ".join(instr_line), test
                ))
                not_found_instructions_count += 1

    tested_instr_count = 0

    with open(arguments.output, "w") as f:
        f.write("Instruction;%s\n" % ";".join(tests))
        for instr_desc, instr_tests in instructions.items():
            f.write("%s%s%s;%s\n" % (
                instr_desc[0],
                " " if len(instr_desc) > 1 else "",
                ", ".join(ModeToStr[arg] for arg in instr_desc[1:]),
                ";".join(
                    ("+" if test in instr_tests else "") for test in tests
                )
            ))
            if instr_tests:
                tested_instr_count += 1

    if arguments.summary:
        summary_stat = OrderedDict()
        for instr_desc, instr_tests in instructions.items():
            instr = instr_desc[0]
            summary_stat[instr] = summary_stat.get(instr, 0) + len(instr_tests)

        summary_text = "\n".join(
            ";".join(map(str, item)) for item in summary_stat.items()
        )
        with open(arguments.summary, "w") as f:
            f.write(summary_text)

    instructions_count = len(instructions)
    if instructions_count:
        print("Coverage: %.2f%% (%d from %d)" % (
            100.0 * tested_instr_count / instructions_count,
            tested_instr_count, instructions_count
        ))
    print("Processed instructions: %d\nNot found Instructions: %d" % (
        processed_instructions_count, not_found_instructions_count
    ))

    return 0


if __name__ == "__main__":
    exit(main())
