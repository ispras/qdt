from os.path import (
    isdir,
    isfile,
    expanduser,
    join,
    splitext
)
from os import (
    mkdir,
    listdir
)
from common import (
    ee
)
from subprocess import (
    Popen,
    PIPE
)
from source import (
    ctags_parser,
    ctags_lexer
)

ENERGIA_PATH = ee("ENERGIA_PATH")
TOOLCHAIN_PATH = join(ENERGIA_PATH, "hardware", "tools", "msp430", "bin")

GPP = join(TOOLCHAIN_PATH, "msp430-g++")
GCC = join(TOOLCHAIN_PATH, "msp430-gcc")

CORE_SFX = ["hardware", "energia", "msp430", "cores", "msp430"]
TOOLCHAIN_INC_SFX = ["hardware", "tools", "msp430", "include"]

ENERGIA_CORE = join(ENERGIA_PATH, *CORE_SFX)


def EI(*tail):
    "Energia Include"
    return "-I" + join(ENERGIA_PATH, *tail)


mcu_flag = "-mmcu=msp430g2553"

target_flags = [
    mcu_flag, # AVR specific options. But! it's not AVR, it's MSP

    "-DF_CPU=16000000L", # macro, CPU frequency

    # IDE specific macros
    "-DARDUINO=10807",
    "-DENERGIA=10807",
    "-DENERGIA_MSP_EXP430G2553LP",
    "-DENERGIA_ARCH_MSP430",

    # IDE specific inclusions
    EI(*TOOLCHAIN_INC_SFX),
    EI(*CORE_SFX),
    EI("hardware", "energia", "msp430", "variants", "MSP-EXP430G2553LP"),
]

small_size_flags = [
    "-Os", # optimize for size

    "-fno-exceptions", # do not generate code for exceptions

    # functions and data items are given its own section. With --gc-sections
    # linker flag it reduces output binary size
    "-ffunction-sections",
    "-fdata-sections",

    "-fno-threadsafe-statics", # do not generate code for thread-safety
]

pass1_gcc_flags = small_size_flags + [
    "-c", # no linking
    "-w", # suppress any warnings

    "-x", "c++", # explicitly set language
    "-E", # stop after preprocessing

    # preprocessor preserves comments and converts C++ comments (//) to
    # C-style comments (/**/) inside macros
    "-CC",
] + target_flags
# the result of this pass is written to (-o) /dev/null

pass2_ctags_flags = [
    "-u", # unsorted
    "--language-force=c++", # explicitly set language

    # Select C++ specific tags
    # s - struct ?
    # v - variable ?
    # p - ?
    # f - function ?
    "--c++-kinds=svpf",

    # Requested output
    # K - Kind of tag as full name
    # z - "kind:" prefix to kind field of tag
    # n - line number of tag definition
    # S - prototypes of functions
    # t - type & name of variable
    # s - scope (?) of tag definition
    # T (removed as unknown) - ?
    "--fields=KStzns",

    "--line-directives", # support #line directives
]

pass3_gcc_flags = small_size_flags + [
    "-c",

    # as may warnings as possible
    "-Wall",
    "-Wextra",

    "-MMD", # generate rules for `make` utility for inclusions in .d file
] + target_flags

lib_gcc_flags = small_size_flags + [
    "-c",

    # as may warnings as possible
    "-Wall",
    "-Wextra",
] + target_flags

pass4_link_flags = [
    "-w",

    "-Os",
    "-fno-rtti",
    "-fno-exceptions",

    "-W" + ",".join([
        "l",
        "--gc-sections",
        "-u",
        "main"
    ]),

    mcu_flag,

    "-L" + join(ENERGIA_PATH, *TOOLCHAIN_INC_SFX),
]

MODULE_EXT = set([".c", ".cpp"])


def iter_modules(root):
    for node in listdir(root):
        full_name = join(root, node)
        if not isfile(full_name):
            continue

        ext = splitext(node)[1]
        if ext in MODULE_EXT:
            yield full_name, node


def Run(*a, **kw):
    print(" ".join(a[0]))
    kw["stdin"] = PIPE
    kw["stdout"] = PIPE
    kw["stderr"] = PIPE
    return Popen(*a, **kw)


class CFunction(object):
    __slots__ = ("name", "has_prototype", "line", "prototype", "t")

    def __init__(self, name):
        self.name = name
        self.has_prototype = False


def main():
    if not isdir("build"):
        mkdir("build")

    core_objs = []

    # TODO: also build avr folder
    for src, sfx in sorted(iter_modules(ENERGIA_CORE)):
        obj = join("build", splitext(sfx)[0] + ".o")

        print("%s -> %s" % (sfx, obj))

        gcc = Run([GPP] + lib_gcc_flags + ["-o", obj, src])
        rc = gcc.wait()
        gccout, gccerr = gcc.stdout.read(), gcc.stderr.read()

        if gccerr:
            print(gccerr)
        if gccout:
            print(gccout)

        if rc:
            return

        core_objs.append(obj)

    ino = join(expanduser("~"), "Energia", "ASCIITable", "ASCIITable.ino")

    # print(" ".join(pass1_gcc_flags))

    p1 = Run([GPP] + pass1_gcc_flags + [ino, "-"])
    p1out, p1err = p1.communicate()

    ctags_target = ino + ".4ctags"

    if p1err:
        print(p1err)
        return
    else:
        print("pre-processed\n\n")
        print(p1out)

    with open(ctags_target, "wb") as f:
        f.write(p1out)

    p2 = Run(["ctags", "-f", "-"] + pass2_ctags_flags + [ctags_target])

    p2out, p2err = p2.communicate()

    print("\n\nctags\n\n")

    if p2err:
        print(p2err)
        return
    else:
        print(p2out)

    ctags = ino + ".ctags"

    with open(ctags, "wb") as f:
        f.write(p2out)

    functions = {}

    ctags = ctags_parser.parse(p2out, lexer = ctags_lexer)

    for t in ctags.tags:
        if t.kind == "prototype":
            f = functions.setdefault(t.name, CFunction(t.name))
            f.has_prototype = True
        elif t.kind == "function":
            f = functions.setdefault(t.name, CFunction(t.name))
            f.line = int(t.line)
        f.t = t

    # this functions are known to have prototypes in headers
    for f in [
        # by Energia.h
        "loop",
        "setup"
    ]:
        functions[f].has_prototype = True

    # some ctags based preprocessing is required

    with open(ino, "rb") as fin:
        ino_content = fin.read()

    ino_lines = ino_content.splitlines()

    # recover prototypes
    for f in functions.values():
        if f.has_prototype:
            continue

        braces = 0
        prototype = ""
        for l in ino_lines[f.line - 1:]:
            for c in l:
                prototype += c
                if c == "(":
                    braces += 1
                elif c == ")":
                    braces -= 1
                    if braces == 0:
                        break
            else:
                continue
            break
        else:
            raise RuntimeError("Cannot get end of function prototype %s" % f.t)

        print(f.name + ": " + repr(prototype))

        f.prototype = prototype

    # add prototype (forward declarations) for each function which have no one
    ino_content = "\n" + ino_content

    for f in functions.values():
        if f.has_prototype:
            continue
        ino_content = f.prototype + ";\n" + ino_content

    # add Energia header inclusion
    ino_content = "#include <Energia.h>\n\n" + ino_content

    cpp = ino + ".cpp"

    with open(cpp, "wb") as fout:
        fout.write(ino_content)

    obj = ino + ".o"

    p3 = Run([GPP] + pass3_gcc_flags + [cpp, "-o", obj])
    p3out, p3err = p3.communicate()

    print("\n\ncompile")
    if p3out:
        print("\nstdout\n\n" + p3out)
    if p3err:
        errs = ino + ".errs"
        with open(errs, "wb") as f:
            f.write(p3err)

        print("\nstderr\n\n" + p3err)

    if p3.returncode != 0:
        # GPP failed to compile
        return

    elf = ino + ".elf"

    p4 = Run([GCC] + pass4_link_flags +
        ["-o", elf, obj] +
        # core_objs +
        # TODO: get it by self using msp430-ar rcs
        ["/tmp/arduino_build_393450/core/core.a"] +
        ["-L" + "build"] +
        # ["-L/tmp/arduino_build_393450"] +
        ["-lm"]
    )
    p4out, p4err = p4.communicate()
    print("\n\nlink")
    if p4out:
        print("\nstdout\n\n" + p4out)
    if p4err:
        print("\nstderr\n\n" + p4err)

    if p4.returncode != 0:
        # GPP failed to link
        return

if __name__ == "__main__":
    main()
