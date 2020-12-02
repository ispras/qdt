from os.path import (
    exists,
    dirname,
    isdir,
    join,
    splitext
)
from os import (
    sep,
    mkdir,
    listdir
)
from common import (
    makedirs,
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
from argparse import (
    ArgumentParser,
)


ENERGIA_PATH = ee("ENERGIA_PATH")
TOOLCHAIN_PATH = join(ENERGIA_PATH, "hardware", "tools", "msp430", "bin")

GPP = join(TOOLCHAIN_PATH, "msp430-g++")
GCC = join(TOOLCHAIN_PATH, "msp430-gcc")
AR = join(TOOLCHAIN_PATH, "msp430-ar")
OBJCOPY = join(TOOLCHAIN_PATH, "msp430-objcopy")
READELF = join(TOOLCHAIN_PATH, "msp430-readelf")

CORE_SFX = ["hardware", "energia", "msp430", "cores", "msp430"]
TOOLCHAIN_INC_SFX = ["hardware", "tools", "msp430", "include"]

ENERGIA_CORE = join(ENERGIA_PATH, *CORE_SFX)
DEBUG = True

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

small_size_flags = ([] if DEBUG else [
    "-Os", # optimize for size
]) + [
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
] + target_flags + ([
    "-O0", "-g"
] if DEBUG else [])
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
] + target_flags + ([
    "-O0", "-g"
] if DEBUG else [])

lib_gcc_flags = small_size_flags + [
    "-c",

    # as may warnings as possible
    "-Wall",
    "-Wextra",
] + target_flags + ([
    "-O0", "-g"
] if DEBUG else [])

pass4_link_flags = ([
    "-O0", "-g"
] if DEBUG else [
    "-Os",
]) + [
    # "-w", # Inhibit all warning messages.
    "-fno-rtti", # do not generate code for runtime type identification
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

readelf_flags = [
    "--all",
    "--section-details",
]

pass5_objcopy_eeprom_flags = [
    "-O", "ihex",
    "-j", ".eeprom",
    "--set-section-flags=.eeprom=alloc,load",
    "--no-change-warnings",
    "--change-section-lma", ".eeprom=0"
]

pass5_objcopy_noeeprom_flags = [
    "-O", "ihex",
    "-R", ".eeprom"
]

MODULE_EXT = set([".c", ".cpp"])


def iter_modules(root, prefix = ""):
    for node in listdir(root):
        full_name = join(root, node)
        if isdir(full_name):
            for tmp in iter_modules(full_name, prefix = prefix + node + sep):
                yield tmp
            continue

        ext = splitext(node)[1]
        if ext in MODULE_EXT:
            yield full_name, prefix + node


class Run(Popen):

    def __init__(self, *a, **kw):
        kw["stdin"] = PIPE
        kw["stdout"] = PIPE
        kw["stderr"] = PIPE
                # Note, `Popen.encoding` is not availble in Py2.
        self.__encoding = kw.pop("encoding", "utf-8")

        self.__verbose = kw.pop("verbose", True)

        if self.__verbose:
            print(" ".join(a[0]))

        super(Run, self).__init__(*a, **kw)

    def communicate(self, input = None, **kw):
        if input is not None:
            input = input.encode(self.__encoding)
        out, err = super(Run, self).communicate(input = input, **kw)
        return out.decode(self.__encoding), err.decode(self.__encoding)


class CFunction(object):
    __slots__ = ("name", "has_prototype", "line", "prototype", "t")

    def __init__(self, name):
        self.name = name
        self.has_prototype = False


def main():
    ap = ArgumentParser(
        description = ".ino file compiller for MSP430"
    )
    ap.add_argument("ino",
        nargs = 1,
        help = "*.ino file to compile"
    )

    args = ap.parse_args()

    if not isdir("build"):
        mkdir("build")

    core_objs = []

    for src, sfx in sorted(iter_modules(ENERGIA_CORE)):
        obj = join("build", splitext(sfx)[0] + ".o")

        objdir = dirname(obj)
        if objdir:
            makedirs(objdir, exist_ok = True)

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

    core = join("build", "core.a")
    if not exists(core):
        for obj in core_objs:
            ar = Run([AR, "rcs", core, obj])
            arrc = ar.wait()

            arout, arerr = ar.stdout.read(), ar.stderr.read()

            print("ar " + obj)

            if arerr:
                print(arerr)
            if arout:
                print(arout)

            if arrc:
                return

    ino = args.ino[0]

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
        f.write(p1out.encode("utf-8"))

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
        f.write(p2out.encode("utf-8"))

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
        ino_content = fin.read().decode("utf-8")

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
        fout.write(ino_content.encode("utf-8"))

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

    # because of multiple definition of `__isr_9' and `__isr_8'
    core_objs = [f for f in core_objs if "Tone.o" not in f]

    p4 = Run([GCC] + pass4_link_flags +
        ["-o", elf, obj] +
        core_objs +
        # [ core ] +
        ["-L" + "build"] +
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

    readelf = Run([READELF] + readelf_flags + [elf])
    readelf.wait()
    reout, reerr = readelf.communicate()
    if reerr:
        print("readelf stderr\n\n" + reerr)

    elftxt = elf + ".txt"
    with open(elftxt, "wb") as f:
        f.write(reout.encode("utf-8"))

    eep = ino + ".eep.hex"

    p5 = Run([OBJCOPY] + pass5_objcopy_eeprom_flags + [elf, eep])
    p5.wait()
    p5out, p5err = p5.communicate()
    print("\n\nmake eeprom")
    if p5out:
        print("\nstdout\n\n" + p5out)
    if p5err:
        print("\nstderr\n\n" + p5err)

    if p5.returncode != 0:
        # objcopy failed
        return

    _hex = ino + ".hex"
    p5_2 = Run([OBJCOPY] + pass5_objcopy_noeeprom_flags + [elf, _hex])
    p5_2.wait()
    p5_2out, p5_2err = p5_2.communicate()
    print("\n\nmake noeeprom")
    if p5_2out:
        print("\nstdout\n\n" + p5_2out)
    if p5_2err:
        print("\nstderr\n\n" + p5_2err)

    if p5_2.returncode != 0:
        # objcopy failed
        return


if __name__ == "__main__":
    main()
