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
    defaultdict,
    OrderedDict
)
from common import (
    mlget as _,
    ee
)
from operator import (
    itemgetter
)
from codecs import (
    open
)


PRINT_IGNORED_LINES = ee("TESTS_COVERAGE_PRINT_IGNORED_LINES", "False")
PRINT_IGNORED_SECTIONS = ee("TESTS_COVERAGE_PRINT_IGNORED_SECTIONS", "False")


# msp430x instruction set description based on:
# doc1: SLAU208Q - MSP430x5xx and MSP430x6xx Family
# doc2: SLAU144J - MSP430x2xx Family

# addressing modes


class RegisterMode:
    pass


class RegisterModeR0(RegisterMode):
    pass


class RegisterModeR1(RegisterMode):
    pass


class RegisterModeR2(RegisterMode):
    pass


# Note: impossible as source register - interpreted as 0 constant ("R3, As = 00", doc2 page 46)
# pointless as destination register - cannot be used as source
#class RegisterModeR3(RegisterMode):
#    pass


# R4-R15 registers
class RegisterModeRn(RegisterMode):
    pass


class IndexedMode:
    pass


# Note, used for coding SymbolicMode
# class IndexedModeR0(IndexedMode):
#     pass


class IndexedModeR1(IndexedMode):
    pass


# Note, used for coding AbsoluteMode
# class IndexedModeR2(IndexedMode):
#     pass


# Note, used for coding Plus1 mode
# class IndexedModeR3(IndexedMode):
#     pass


# R4-R15 registers
class IndexedModeRn(IndexedMode):
    pass


# X(PC), X(R0) Indexed mode is used for coding
class SymbolicMode:
    pass


# X(SR), X(R2) Indexed mode is used for coding
class AbsoluteMode:
    pass


class IndirectRegisterMode:
    pass


class IndirectRegisterModeR0(IndirectRegisterMode):
    pass


class IndirectRegisterModeR1(IndirectRegisterMode):
    pass


# Note, used for coding Plus4 mode
# class IndirectRegisterModeR2(IndirectRegisterMode):
#     pass


# Note, used for coding Plus2 mode
# class IndirectRegisterModeR3(IndirectRegisterMode):
#     pass


class IndirectRegisterModeRn(IndirectRegisterMode):
    pass


class IndirectAutoincrementMode:
    pass


# Note, used for coding Immediate mode for all instructions, except MOVA and
# its emulated instructions
class IndirectAutoincrementModeR0(IndirectAutoincrementMode):
    pass


class IndirectAutoincrementModeR1(IndirectAutoincrementMode):
    pass


# Note, used for coding Plus8 mode
# class IndirectAutoincrementModeR2(IndirectAutoincrementMode):
#     pass


# Note, used for coding Minus1 mode
# class IndirectAutoincrementModeR3(IndirectAutoincrementMode):
#     pass


# R4-R15 registers
class IndirectAutoincrementModeRn(IndirectAutoincrementMode):
    pass


# @PC+ Indirect Autoincrement mode is used for coding
class ImmediateMode:
    pass


# $N
class LabelMode:
    pass


class ConstantGenerator:
    pass


# ("R2, As = 10", doc1 page 193)
class Plus4(ConstantGenerator):
    pass


# ("R2, As = 11", doc1 page 193)
class Plus8(ConstantGenerator):
    pass


# ("R3, As = 00", doc1 page 193)
class Zero(ConstantGenerator):
    pass


# ("R3, As = 01", doc1 page 193)
class Plus1(ConstantGenerator):
    pass


# ("R3, As = 10", doc1 page 193)
class Plus2(ConstantGenerator):
    pass


# ("R3, As = 11", doc1 page 193)
class Minus1(ConstantGenerator):
    pass


ModeToStr = {
    RegisterModeR0: "PC",
    RegisterModeR1: "SP",
    RegisterModeR2: "SR",
    # RegisterModeR3: "R3",
    RegisterModeRn: "Rn",
    # IndexedModeR0: "X(PC)",
    IndexedModeR1: "X(SP)",
    # IndexedModeR2: "X(SR)",
    # IndexedModeR3: "X(R3)",
    IndexedModeRn: "X(Rn)",
    SymbolicMode: "ADDR",
    AbsoluteMode: "&ADDR",
    IndirectRegisterModeR0: "@PC",
    IndirectRegisterModeR1: "@SP",
    IndirectRegisterModeRn: "@Rn",
    IndirectAutoincrementModeR0: "@PC+",
    IndirectAutoincrementModeR1: "@SP+",
    # IndirectAutoincrementModeR2: "@SR+",
    # IndirectAutoincrementModeR3: "@R3+",
    IndirectAutoincrementModeRn: "@Rn+",
    ImmediateMode: "#N",
    LabelMode: "$N",
    Plus4: "#4",
    Plus8: "#8",
    Zero: "#0",
    Plus1: "#1",
    Plus2: "#2",
    Minus1: "#-1"
}

RegisterModes = [
    RegisterModeR0,
    RegisterModeR1,
    RegisterModeR2,
    # RegisterModeR3, # doc2 page 46 - R3 used for CG
    RegisterModeRn
]

OtherModes = [
    IndexedModeR1,
    IndexedModeRn,
    SymbolicMode,
    AbsoluteMode,
    IndirectRegisterModeR0,
    IndirectRegisterModeR1,
    IndirectRegisterModeRn,
    IndirectAutoincrementModeR1,
    IndirectAutoincrementModeRn
]

ImmediateModes = [
    Plus4,
    Plus8,
    Zero,
    Plus1,
    Plus2,
    Minus1,
    ImmediateMode # other values
]

SrcAddrModes = RegisterModes + OtherModes + ImmediateModes

DstAddrModes = RegisterModes + [
    IndexedModeR1,
    # TODO: IndexedModeR3 for dst possible?
    IndexedModeRn,
    SymbolicMode,
    AbsoluteMode
]


def parse_arg_mode(instr, arg):
    # TODO: can't distinguish the Constant Generator value from an Immediate
    if arg[0] == "#":
        tail = arg[1:]
        if tail == "4":
            return Plus4
        elif tail == "8":
            return Plus8
        elif tail == "0":
            return Zero
        elif tail == "1":
            return Plus1
        elif tail == "2":
            return Plus2
        elif tail == "-1":
            return Minus1
        else:
            return ImmediateMode

    if arg[0] == "$":
        return LabelMode

    if arg[0] == "&":
        return AbsoluteMode

    if arg[0] == "@" and arg[1] in ["r", "R"]:
        if arg[-1] == "+":
            tail = arg[2:-1]
            if tail == "0":
                return IndirectAutoincrementModeR0
            elif tail == "1":
                return IndirectAutoincrementModeR1
            # elif tail == "2":
            #     return IndirectAutoincrementModeR2
            # elif tail == "3":
            #     return IndirectAutoincrementModeR3
            else:
                return IndirectAutoincrementModeRn
        else:
            tail = arg[2:]
            if tail == "0":
                return IndirectRegisterModeR0
            elif tail == "1":
                return IndirectRegisterModeR1
            else:
                return IndirectRegisterModeRn

    if arg[-4:]  in ["(r0)", "(R0)"]:
        return SymbolicMode

    if arg[-1] == ")":
        tail = arg.split("(")[1][1:-1]
        if tail == "1":
            return IndexedModeR1
        else:
            return IndexedModeRn

    if arg[0] in ["r", "R"]:
        tail = arg[1:]
        if tail == "0":
            return RegisterModeR0
        elif tail == "1":
            return RegisterModeR1
        elif tail == "2":
            return RegisterModeR2
        # see notes about RegisterModeR3
        # elif tail == "3":
        #     return RegisterModeR3
        else:
            return RegisterModeRn

    raise RuntimeError("Mode not recognized: %s (%s)" % (arg, instr))

instructions = OrderedDict()
mnemonic_aliases = {}
emulated2real_instructions = {}
real2emulated_instructions = defaultdict(list)

not_found_mnemonics = defaultdict(int)

def FI(name,
    AddrMode1 = SrcAddrModes,
    AddrMode2 = DstAddrModes,
    flags = [".W", ".B"]
):
    for flag in flags:
        for arg1Type in AddrMode1:
            for arg2Type in AddrMode2:
                # doc2 page 45:
                # SR can be used in the register mode only addressed with word
                # instructions
                if (    (   arg1Type == RegisterModeR2
                         or arg2Type == RegisterModeR2
                    )
                    and flag != ".W"
                ):
                    continue
                instructions[
                    (name + flag, arg1Type, arg2Type)
                ] = []
    if ".W" in flags:
        mnemonic_aliases[name] = name + ".W"

def FII(name, AddrMode = DstAddrModes, flags = [".W", ".B"]):
    for flag in flags:
        if AddrMode:
            for arg1Type in AddrMode:
                instructions[(name + flag, arg1Type)] = []
        else:
            instructions[(name + flag,)] = []
    if ".W" in flags:
        mnemonic_aliases[name] = name + ".W"

def J(name):
    instructions[(name, LabelMode)] = []

def A(name,
    AddrMode1 = RegisterModes + ImmediateModes,
    AddrMode2 = RegisterModes
):
    for arg1Type in AddrMode1:
        for arg2Type in AddrMode2:
            instructions[(name, arg1Type, arg2Type)] = []

def add_e_instr(emulated_instr, real_instr):
    # add emulated instruction to dictionary
    emulated2real_instructions[emulated_instr] = real_instr
    real2emulated_instructions[real_instr].append(emulated_instr)

def gen_e_instrs(new_name, old_name, arg1 = None, arg2 = None):
    # search real instructions by pattern and add emulated instruction
    if arg1 is not None and arg2 is not None:
        raise RuntimeError("At least one of the args must be None")
    for i in instructions:
        if i[0] == old_name:
            if arg2 and i[2] == arg2:
                # Case: instr src -> instr src, FIXED
                add_e_instr((new_name, i[1]), i)
            elif arg1 and i[1] == arg1:
                # Case: instr dst -> instr FIXED, dst
                add_e_instr((new_name, i[2]), i)
            elif arg1 is None and arg2 is None and i[1] == i[2]:
                # Case: instr dst -> instr dst, dst
                add_e_instr((new_name, i[1]), i)

def gen_e_instrs_wb(new_name, old_name, arg1 = None, arg2 = None):
    # add W or B flags to mnemonic before search real instruction
    gen_e_instrs(new_name + ".W", old_name + ".W", arg1, arg2)
    mnemonic_aliases[new_name] = new_name + ".W"
    gen_e_instrs(new_name + ".B", old_name + ".B", arg1, arg2)

def gen_e_instrs_awb(new_name, old_name, arg1 = None, arg2 = None):
    # add A, W or B flags to mnemonic before search real instruction
    gen_e_instrs(new_name + ".A", old_name + ".A", arg1, arg2)
    gen_e_instrs(new_name + ".W", old_name + ".W", arg1, arg2)
    mnemonic_aliases[new_name] = new_name + ".W"
    gen_e_instrs(new_name + ".B", old_name + ".B", arg1, arg2)

def instr_to_str(instr):
    return "%s%s%s" % (
        instr[0],
        " " if len(instr) > 1 else "",
        ", ".join(ModeToStr[arg] for arg in instr[1:])
    )

def fill_instructions(with_x_instrs):
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
        if with_x_instrs:
            FI(i + "X", flags = [".A", ".W", ".B"])

    # MSP430 Single-Operand (Format II) Instructions
    for i in [
        ("RRC", RegisterModes + OtherModes), # doc2 page 145 - all modes except Immediate
        ("RRA", RegisterModes + OtherModes), # doc2 page 145 - all modes except Immediate
        ("PUSH", SrcAddrModes), # arg is src (not dst)
        ("SWPB", RegisterModes + OtherModes, [""]), # doc2 page 145 - all modes except Immediate, no flag
        ("CALL", SrcAddrModes, [""]), # no flag
        ("RETI", None, [""]), # no explicit dst, no flag
        ("SXT", RegisterModes + OtherModes, [""]) # doc2 page 145 - all modes except Immediate, no flag
    ]:
        FII(*i)

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
    mnemonic_aliases["JLO"] = "JNC"
    mnemonic_aliases["JHS"] = "JC"

    # MSP430 Emulated Instructions
    gen_e_instrs_wb("ADC", "ADDC", Zero)
    gen_e_instrs("BR", "MOV.W", arg2 = RegisterModeR0)
    gen_e_instrs_wb("CLR", "MOV", Zero)
    add_e_instr(("CLRC",), ("BIC.W", Plus1, RegisterModeR2))
    add_e_instr(("CLRN",), ("BIC.W", Plus4, RegisterModeR2))
    add_e_instr(("CLRZ",), ("BIC.W", Plus2, RegisterModeR2))
    gen_e_instrs_wb("DADC", "DADD", Zero)
    gen_e_instrs_wb("DEC", "SUB", Plus1)
    gen_e_instrs_wb("DECD", "SUB", Plus2)
    add_e_instr(("DINT",), ("BIC.W", Plus8, RegisterModeR2))
    add_e_instr(("EINT",), ("BIS.W", Plus8, RegisterModeR2))
    gen_e_instrs_wb("INC", "ADD", Plus1)
    gen_e_instrs_wb("INCD", "ADD", Plus2)
    gen_e_instrs_wb("INV", "XOR", Minus1)
    #add_e_instr(("NOP",), ("MOV.W", Zero, RegisterModeR3))
    instructions[("NOP",)] = [] # add as non-emulated instruction, because RegisterModeR3 gone
    gen_e_instrs("POP", "MOV.W", IndirectAutoincrementModeR1)
    add_e_instr(("RET",), ("MOV.W", IndirectAutoincrementModeR1, RegisterModeR0))
    gen_e_instrs_wb("RLA", "ADD")
    gen_e_instrs_wb("RLC", "ADDC")
    gen_e_instrs_wb("SBC", "SUBC", Zero)
    add_e_instr(("SETC",), ("BIS.W", Plus1, RegisterModeR2))
    add_e_instr(("SETN",), ("BIS.W", Plus4, RegisterModeR2))
    add_e_instr(("SETZ",), ("BIS.W", Plus2, RegisterModeR2))
    gen_e_instrs_wb("TST", "CMP", Zero)

    if not with_x_instrs:
        return

    # MSP430X Extended Single-Operand (Format II) Instructions
    for i in [
        ("CALLA", DstAddrModes, [""]),
        ("POPM", RegisterModes, [".A", ".W"]),
        ("PUSHM", RegisterModes, [".A", ".W"]),
        ("PUSHX", SrcAddrModes, [".A", ".W", ".B"]), # arg is src (not dst)
        ("RRCM", RegisterModes, [".A", ".W"]),
        ("RRUM", RegisterModes, [".A", ".W"]),
        ("RRAM", RegisterModes, [".A", ".W"]),
        ("RLAM", RegisterModes, [".A", ".W"]),
        ("RRCX", DstAddrModes, [".A", ".W", ".B"]),
        ("RRUX", RegisterModes, [".A", ".W", ".B"]), # Rdst operand
        ("RRAX", DstAddrModes, [".A", ".W", ".B"]), # TODO: no immediate mode (doc1 page 226)?
        ("SWPBX", DstAddrModes, [".A", ".W"]),
        ("SXTX", DstAddrModes, [".A", ".W"])
    ]:
        FII(*i)

    # MSP430X Address Instructions
    for i in [
        "ADDA",
        #"MOVA", # moved to a separate case
        "CMPA",
        "SUBA"
    ]:
        A(i)

    # TODO: no SymbolicMode for dst?
    A("MOVA", SrcAddrModes + [IndirectAutoincrementModeR0], RegisterModes)
    A("MOVA", RegisterModes, [IndexedMode, AbsoluteMode])

    # MSP430X Extended Emulated Instructions
    # Note, CLRA, DECDA, INCDA, TSTA do not require additional checking of the 2nd
    # argument, since there are only real instructions like "#imm, Rdst"
    gen_e_instrs_awb("ADCX", "ADDCX", Zero)
    gen_e_instrs("BRA", "MOVA", arg2 = RegisterModeR0)
    add_e_instr(("RETA",), ("MOVA", IndirectAutoincrementModeR1, RegisterModeR0))
    gen_e_instrs("CLRA", "MOVA", Zero) # MOVA: doc2 page 155 - mistake, doc2 page 263 - true TODO CHECK
    gen_e_instrs_awb("CLRX", "MOVX", Zero)
    gen_e_instrs_awb("DADCX", "DADDX", Zero)
    gen_e_instrs_awb("DECX", "SUBX", Plus1)
    gen_e_instrs("DECDA", "SUBA", Plus2)
    gen_e_instrs_awb("DECDX", "SUBX", Plus2)
    gen_e_instrs_awb("INCX", "ADDX", Plus1)
    gen_e_instrs("INCDA", "ADDA", Plus2)
    gen_e_instrs_awb("INCDX", "ADDX", Plus2)
    gen_e_instrs_awb("INVX", "XORX", Minus1)
    gen_e_instrs_awb("RLAX", "ADDX")
    gen_e_instrs_awb("RLCX", "ADDCX")
    gen_e_instrs_awb("SBCX", "SUBCX", Zero) # SUBCX: doc2 page 155 - true, doc2 page 249 - mistake TODO CHECK
    gen_e_instrs("TSTA", "CMPA", Zero)
    gen_e_instrs_awb("TSTX", "CMPX", Zero)
    gen_e_instrs_awb("POPX", "MOVX", IndirectAutoincrementModeR1)

def arg_type_directory(string):
    if not isdir(string):
        raise ArgumentTypeError(string + " is not directory")
    return string

def zip_with_scalar(l, o):
    return list(zip(l, [o] * len(l)))

def main():
    parser = ArgumentParser(description = "MSP430x tests coverage")

    parser.add_argument(
        "irdirs",
        nargs = "*",
        default = [],
        type = arg_type_directory,
        metavar = "/path/to/c2t/tests/ir/directory",
        help = "Paths to directories with disas files from C2T tests"
    )
    parser.add_argument("-o", "--output",
        metavar = "coverage.csv",
        default = "ir_disas_table.csv",
        help = "Name of output verbose coverage table",
    )
    parser.add_argument("-s", "--summary",
        metavar = "summary.csv",
        help = "Name of coverage summary table (name and some counters)"
    )
    parser.add_argument("-a", "--addressing-modes",
        metavar = "coverage_addressing_modes.csv",
        help = "Name of coverage addressing modes table"
    )
    parser.add_argument("-x", "--xinstrs",
        action = "store_true",
        help = "Add coverage of extended instructions"
    )
    parser.add_argument("-m", "--markdown",
        action = "store_true",
        help = "Generate all selected tables in markdown format too"
    )
    parser.add_argument("-b", "--boardtests",
        nargs = "*",
        default = [],
        type = arg_type_directory,
        metavar = "/path/to/asm/ir/directory",
        # Note: process code between "test" and "_unexpected_" labels only
        help = "Paths to directories with disas files from asm tests"
    )

    arguments = parser.parse_args()

    irdirs = []
    if arguments.irdirs:
        irdirs.extend(zip_with_scalar(arguments.irdirs, False))
    if arguments.boardtests:
        irdirs.extend(zip_with_scalar(arguments.boardtests, True))
    if not irdirs:
        parser.error("at least one directory with disas files is needed")

    fill_instructions(arguments.xinstrs)

    tests = []
    line_with_label = compile("^[0-9a-f]+ <(.+)>:$")
    line_with_instr = compile(
        "^ +[0-9a-f]+:\t" # offset
        "(?:[0-9a-f][0-9a-f] )+ *\t" # machine code
        "([^;]+?)" # assembly code
        " *\t*(?:;.*)?$" # comment
    )
    instr_to_parts = compile(
        "^([^ \t,]+)" # mnemonic
        "(?:\t([^ \t,]+)" # first argument
        "(?:,\t?([^ \t,]+))?)?$" # second argument
    )

    processed_instructions_count = 0
    not_parsed_instructions_count = 0
    not_found_instructions_count = 0

    ignored_sections = set()

    for i, (irdir, asm_test) in enumerate(irdirs):
        for irfile in glob(join(abspath(irdir), "*.disas")):
            test = splitext(basename(irfile))[0]
            if test in tests:
                # add dir sequential number to make unique test name
                test = test + "#" + str(i)
            tests.append(test)
            with open(irfile, "r") as f:
                lines = f.readlines()

            ignore_section = True
            ignore_code = True

            for line in lines:
                if "Disassembly of section " in line:
                    section_name = line[23:-2]
                    ignore_section = section_name not in [".lowtext", ".text"]
                    if ignore_section:
                        ignored_sections.add(section_name)
                    continue
                else:
                    if ignore_section:
                        continue

                if asm_test:
                    mi = line_with_label.match(line)
                    if mi:
                        label = mi.group(1)
                        if label == "test":
                            ignore_code = False
                        elif label == "_unexpected_":
                            ignore_code = True
                    if ignore_code:
                        continue

                mi = line_with_instr.match(line)
                if not mi:
                    if PRINT_IGNORED_LINES:
                        line_strip = line.strip()
                        # show message only for lines with some text
                        if len(line_strip) > 0:
                            print('IGNORED: "%s" from "%s"' % (
                                line_strip, test
                            ))
                    continue

                assembly_code = mi.group(1)

                if "rpt" in assembly_code:
                    # TODO: the repeat prefix is simply discarded
                    # need accounting?
                    assembly_code = assembly_code.split("{")[1][1:]

                message = '"%s" from "%s"' % (assembly_code, test)

                mi = instr_to_parts.match(assembly_code)
                if not mi:
                    print("NOT PARSED: %s" % message)
                    not_parsed_instructions_count += 1
                    continue

                instr_mnem = mi.group(1).upper()
                instr_mnem = mnemonic_aliases.get(instr_mnem, instr_mnem)

                if mi.group(3):
                    # instruction with 2 arguments
                    src_mode = parse_arg_mode(message, mi.group(2))
                    dst_mode = parse_arg_mode(message, mi.group(3))

                    if instr_mnem in [
                        "POPM.W", "POPM.A",
                        "PUSHM.W", "PUSHM.A",
                        "RRCM.W", "RRCM.A",
                        "RRUM.W", "RRUM.A",
                        "RRAM.W", "RRAM.A",
                        "RLAM.W", "RLAM.A"
                    ]:
                        # doc2 page 154
                        # the source argument coded without CG or Immediate
                        # the value doesn't matter
                        instr = (instr_mnem, dst_mode)
                    else:
                        instr = (instr_mnem, src_mode, dst_mode)
                elif mi.group(2):
                    # instruction with 1 argument
                    arg_mode = parse_arg_mode(message, mi.group(2))
                    instr = (instr_mnem, arg_mode)
                else:
                    # instruction without arguments
                    instr = (instr_mnem,)

                instr = emulated2real_instructions.get(instr, instr)

                try:
                    instructions[instr].append(test)
                    processed_instructions_count += 1
                except KeyError:
                    print("NOT FOUND: %s" % message)
                    not_found_instructions_count += 1
                    not_found_mnemonics[instr_mnem] += 1

    tested_instr_count = 0

    with open(arguments.output, "w") as f:
        f.write("Instruction;Emulated;Tests%s\n" % (";" * (len(tests) - 1)))
        f.write(";;%s\n" % ";".join(tests))
        for instr_desc, instr_tests in instructions.items():
            f.write("%s;%s;%s\n" % (
                instr_to_str(instr_desc),
                " | ".join(instr_to_str(i)
                    for i in real2emulated_instructions[instr_desc]
                ),
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
            occurences, variants_met, variants_total = (
                summary_stat.get(instr, (0, 0, 0))
            )
            instr_tests_count = len(instr_tests)
            if instr_tests_count > 0:
                occurences += len(instr_tests)
                variants_met += 1
            variants_total += 1
            summary_stat[instr] = (occurences, variants_met, variants_total)

        columns = [
            _("Mnemonic").get(),
            _("Occurrences").get(),
            _("Variants met").get(),
            _("Variants total").get()
        ]

        csv_text = (
            u";".join(columns) + u"\n" +
            u"\n".join(
                u"%s;%s" % (instr, u";".join(map(str, counters)))
                for instr, counters in summary_stat.items()
            )
        )
        with open(arguments.summary, "wb", encoding = "utf-8") as f:
            f.write(csv_text)

        if arguments.markdown:
            columns_len = [len(col) for col in columns]
            row_formatter = (
                u"| " + u" | ".join(u"{:<%d}" % cl for cl in columns_len) +
                u" |\n"
            )
            rows_delimiter = (
                u"+" + u"+".join(u"-" * (cl + 2) for cl in columns_len) +
                u"+\n"
            )

            md_text = (
                rows_delimiter +
                row_formatter.format(*columns) +
                rows_delimiter.replace(u"-", u"=") + # header delimiter
                rows_delimiter.join(
                    row_formatter.format(instr, *counters)
                    for instr, counters in summary_stat.items()
                ) +
                rows_delimiter
            )
            with open(splitext(arguments.summary)[0] + ".md", "wb",
                encoding = "utf-8"
            ) as f:
                f.write(md_text)

    if arguments.addressing_modes:
        FI_arg1 = set()
        FI_arg2 = set()
        FII_arg = set()
        J_arg = False
        for instr_desc, instr_tests in instructions.items():
            if len(instr_tests) == 0:
                continue
            instr_desc_len = len(instr_desc)
            if instr_desc_len == 3:
                # instruction with 2 arguments
                FI_arg1.add(instr_desc[1])
                FI_arg2.add(instr_desc[2])
            elif instr_desc_len == 2:
                # instruction with 1 argument
                mode = instr_desc[1]
                if mode == LabelMode:
                    J_arg = True
                    continue
                FII_arg.add(instr_desc[1])

        columns = [
            _("Mode").get(),
            _("FI arg1").get(),
            _("FI arg2").get(),
            _("FII arg").get(),
            _("FIII arg").get()
        ]
        columns_len = [len(col) for col in columns]
        columns_len[0] = max(len(s) for s in ModeToStr.values())
        row_formatter = (
            u"| " + u" | ".join(u"{:<%d}" % cl for cl in columns_len) + u" |\n"
        )
        rows_delimiter = (
            u"+" + u"+".join(u"-" * (cl + 2) for cl in columns_len) + u"+\n"
        )

        csv_text = u";".join(columns) + u"\n"
        md_text = rows_delimiter + row_formatter.format(*columns)
        md_text += rows_delimiter.replace(u"-", u"=") # header delimiter

        yes = _("YES").get()
        no =  _("NO").get()
        for mode, s_mode in sorted(
            ModeToStr.items(),
            key = itemgetter(1)
        ):
            # TODO: no IndirectAutoincrementModeR0 in msp430 - ignored
            if mode in [IndirectAutoincrementModeR0]:
                continue

            params = (
                s_mode,
                # Note, empty space - not available
                yes if mode in FI_arg1 else no if mode in SrcAddrModes else "",
                yes if mode in FI_arg2 else no if mode in DstAddrModes else "",
                # Note, not all modes are available for every FII instruction
                yes if mode in FII_arg else no if mode != LabelMode else "",
                (yes if J_arg else no) if mode == LabelMode else ""
            )

            csv_text += u";".join(params) + u"\n"
            md_text += row_formatter.format(*params) + rows_delimiter

            with open(arguments.addressing_modes, "wb",
                encoding = "utf-8"
            ) as f:
                f.write(csv_text)

            if arguments.markdown:
                with open(splitext(arguments.addressing_modes)[0] + ".md",
                    "wb",
                    encoding = "utf-8"
                ) as f:
                    f.write(md_text)

    instructions_count = len(instructions)
    if instructions_count:
        print("Coverage: %.2f%% (%d from %d)" % (
            100.0 * tested_instr_count / instructions_count,
            tested_instr_count, instructions_count
        ))
    print("Processed instructions: %d" % processed_instructions_count)
    if not_parsed_instructions_count > 0:
        print("Not parsed instructions: %d" % not_parsed_instructions_count)
    if not_found_instructions_count > 0:
        print("Not found instructions: %d" % not_found_instructions_count)
        for item in sorted(
            not_found_mnemonics.items(),
            key = itemgetter(1),
            reverse = True
        ):
            print("%s: %d" % item)
    if PRINT_IGNORED_SECTIONS and len(ignored_sections) > 0:
        print("Ignored sections:\n%s" % "\n".join(ignored_sections))

    return 0


if __name__ == "__main__":
    exit(main())
