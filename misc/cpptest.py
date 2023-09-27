from common import (
    qdtdirs,
    makedirs,
)
from libe.common.pypath import (
    pypath,
)
from source import (
    get_cpp_search_paths,
)

from argparse import (
    ArgumentParser,
)
from itertools import (
    chain,
)
from os import (
    walk,
)
from os.path import (
    dirname,
    join,
    sep,
)
from psutil import (
    Process,
)
with pypath("..ply"):
    import ply.cpp
    from ply.cpp import (
        Preprocessor,
    )
    from ply.lex import (
        lex,
    )
from re import (
    compile,
)
from subprocess import (
    PIPE,
    Popen,
)
from time import (
    time,
)

logDrop = lambda __: None
logWrite = logDrop

def log(msg):
    logWrite(msg + "\n")
    print(msg)


systemCPPPaths = get_cpp_search_paths()
CPPLexer = lex(ply.cpp)
proc = Process()


def system_cpp(
    fullInPath,
    CPPPaths = tuple(),
):
    paths_args = []
    for CPPPath in CPPPaths:
        paths_args.append("-I")
        paths_args.append(CPPPath)

    p = Popen(
        ["cpp"]
      + paths_args
      + [
          # preprocess only, as desired
          "-E",
          # no line markers
          "-P",
          # no standard includes (all must be in CPPPaths)
          "-nostdinc",
        ]
      + [fullInPath],
        stdout = PIPE,
        stderr = PIPE,
    )

    stdo, stde = p.communicate()

    if p.wait():
        raise RuntimeError("cpp failed\n" + stde)

    return stdo


def by3(iterable):
    i = iter(iterable)
    for n0 in i:
        try:
            n1 = next(i)
        except StopIteration:
            n1 = ""
            n2 = ""
        else:
            try:
                n2 = next(i)
            except StopIteration:
                n2 = ""
        yield (n0, n1, n2)


def log_mem_usage():
    mu = str(proc.memory_info().rss)
    mu = "_".join(reversed(tuple(
        "".join(reversed(t)) for t in by3(reversed(mu))
    )))
    log("memory:\n\t" + mu)


def main():
    global logWrite

    ap = ArgumentParser()
    arg = ap.add_argument

    arg("-o",
        default = join(qdtdirs.user_cache_dir, "cpptest", str(time())),
        help = "output directory",
        metavar = "output_dir",
    )
    arg("-p",
        default = ".*[.](c|(cpp))$",
        help = "inclusion pattern",
        metavar = "pattern",
    )
    arg("i",
        help = "input directory",
        metavar = "input_dir",
    )
    arg("-I",
        action = "append",
        default = [],
        help = "extra CPP search path for #include",
        metavar = "include_dir",
    )
    arg("--cpp",
        action = "store_true",
        help = "use system cpp",
    )
    arg("-t",
        default = "60.",
        help = "time limit",
        metavar = "seconds",
    )
    arg("--tag",
        default = "",
        help = "a tag for log file",
        metavar = "tag",
    )

    args = ap.parse_args()

    # cache
    inDir = args.i
    pattern = args.p
    outDir = args.o
    CPPPaths = sorted(set(args.I))
    tLimit = float(args.t)
    cpp = args.cpp

    logFileName = join(outDir, "log.txt")
    makedirs(outDir, exist_ok = True)
    logFile = open(logFileName, "w")
    logWrite = logFile.write

    log("logFileName:\n\t" + logFileName)
    log("tag:\n\t" + args.tag)
    log("inDir:\n\t" + inDir)
    log("pattern:\n\t" + pattern)
    log("outDir:\n\t" + outDir)
    log("systemCPPPaths:" + "\n\t-I".join(("",) + systemCPPPaths))
    log("CPPPaths:" + "\n\t-I".join([""] + CPPPaths))
    log("using system cpp:\n\t" + str(cpp))
    log("tLimit:\n\t" + str(tLimit))

    rePattern = compile(pattern)

    # cache
    matches = rePattern.match
    inDirSfxLen = len(inDir) + len(sep)
    pathSlice = slice(inDirSfxLen, None)

    tStart = time()
    total = 0

    inc_cache = None

    allIncPaths = tuple(chain(CPPPaths, systemCPPPaths))

    for dirPath, __, fileNames in walk(inDir):
        for fileName in sorted(fileNames):
            fullInPath = join(dirPath, fileName)
            if not matches(fullInPath):
                continue

            log_mem_usage()

            pathSfx = fullInPath[pathSlice]
            fullOutPath = join(outDir, pathSfx) + ".pp"
            curOutDir = dirname(fullOutPath)

            log(
                str(total) + ": "
                + pathSfx + "\n\t" + fullOutPath
                + " at " + str(time() - tStart)
            )

            makedirs(curOutDir, exist_ok = True)

            outFile = open(fullOutPath, "w")
            # cache
            write = outFile.write

            if cpp:
                outData = system_cpp(fullInPath,
                    CPPPaths = (dirPath,) + allIncPaths,
                )

                write(outData)
            else:
                p = Preprocessor(CPPLexer)

                inData = p.read_include_file(fullInPath)

                if inc_cache is None:
                    if hasattr(p, "inc_cache"):
                        inc_cache = p.inc_cache
                else:
                    p.inc_cache = inc_cache

                p.add_path(dirPath)
                for __ in map(p.add_path, allIncPaths): pass
                p.parse(inData, fullInPath)

                token = p.token

                tok = token()
                while tok:
                    write(tok.value)
                    tok = token()

            outFile.close()

            total += 1
            tEnd = time()
            tTime = tEnd - tStart

            if tTime > tLimit:
                break
        else:
            continue
        break

    log_mem_usage()

    log("total:\n\t" + str(total))
    log("tTime:\n\t" + str(tTime))
    log("speed f/s:\n\t" + str(total / tTime) if tTime else "-")
    log("speed s/f:\n\t" + str(tTime / total) if total else "-")

    logWrite = logDrop
    logFile.close()

if __name__ == "__main__":
    exit(main() or 0)
