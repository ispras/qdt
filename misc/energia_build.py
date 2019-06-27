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

ENERGIA_PATH = ee("ENERGIA_PATH")
TOOLCHAIN_PATH = join(ENERGIA_PATH, "hardware", "tools", "msp430", "bin")

GCC = join(TOOLCHAIN_PATH, "msp430-g++")

CORE_SFX = ["hardware", "energia", "msp430", "cores", "msp430"]
TOOLCHAIN_INC_SFX = ["hardware", "tools", "msp430", "include"]

ENERGIA_CORE = join(ENERGIA_PATH, *CORE_SFX)


def EI(*tail):
    "Energia Include"
    return "-I" + join(ENERGIA_PATH, *tail)


target_flags = [
    "-mmcu=msp430g2553", # AVR specific options. But! it's not AVR, it's MSP

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
    kw["stdin"] = PIPE
    kw["stdout"] = PIPE
    kw["stderr"] = PIPE
    return Popen(*a, **kw)


def main():
    if not isdir("build"):
        mkdir("build")

    core_objs = []

    for src, sfx in iter_modules(ENERGIA_CORE):
        obj = join("build", splitext(sfx)[0] + ".o")

        print("%s -> %s" % (sfx, obj))

        gcc = Run([GCC] + lib_gcc_flags + ["-o", obj, src])
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

    p1 = Run([GCC] + pass1_gcc_flags + [ino, "-"])
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

    cpp = ino + ".cpp"

    # TODO: some ctags based preprocessing is required
    with open(ino, "rb") as fin:
        with open(cpp, "wb") as fout:
            fout.write(fin.read())

    obj = ino + ".obj"

    p3 = Run([GCC] + pass3_gcc_flags + [cpp, "-o", obj])
    p3out, p3err = p3.communicate()

    print("\n\ncompile")
    if p3out:
        print("\nstdout\n\n" + p3out)
    if p3err:
        print("\nstderr\n\n" + p3err)


if __name__ == "__main__":
    main()
