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
        default = ".*[.](h|c|(cpp)|(hpp))$",
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
    arg("-t",
        default = "60.",
        help = "time limit",
        metavar = "seconds",
    )

    args = ap.parse_args()

    # cache
    inDir = args.i
    pattern = args.p
    outDir = args.o
    CPPPaths = sorted(set(args.I))
    tLimit = float(args.t)

    logFileName = join(outDir, "log.txt")
    makedirs(outDir, exist_ok = True)
    logFile = open(logFileName, "w")
    logWrite = logFile.write

    log("logFileName   : " + logFileName)
    log("inDir         : " + inDir)
    log("pattern       : " + pattern)
    log("outDir        : " + outDir)
    log("systemCPPPaths:" + "\n\t-I".join(("",) + systemCPPPaths))
    log("CPPPaths      :" + "\n\t-I".join([""] + CPPPaths))
    log("tLimit        : " + str(tLimit))

    rePattern = compile(pattern)

    # cache
    matches = rePattern.match
    inDirSfxLen = len(inDir) + len(sep)
    pathSlice = slice(inDirSfxLen, None)

    tStart = time()
    total = 0

    inc_cache = None

    for dirPath, __, fileNames in walk(inDir):
        for fileName in fileNames:
            fullInPath = join(dirPath, fileName)
            if not matches(fullInPath):
                continue

            pathSfx = fullInPath[pathSlice]
            fullOutPath = join(outDir, pathSfx) + ".pp"
            curOutDir = dirname(fullOutPath)

            log(
                str(total) + ": "
                + pathSfx + " -> " + fullOutPath
                + " at " + str(time() - tStart)
            )

            makedirs(curOutDir, exist_ok = True)

            p = Preprocessor(CPPLexer)

            inData = p.read_include_file(fullInPath)

            outFile = open(fullOutPath, "w")

            if inc_cache is None:
                if hasattr(p, "inc_cache"):
                    inc_cache = p.inc_cache
            else:
                p.inc_cache = inc_cache

            for __ in map(p.add_path, chain(CPPPaths, systemCPPPaths)): pass
            p.parse(inData, fullInPath)

            # cache
            write = outFile.write
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

    log("total    : " + str(total))
    log("tTime    : " + str(tTime))
    log("speed f/s: " + str(total / tTime) if tTime else "-")
    log("speed s/f: " + str(tTime / total) if total else "-")

    logWrite = logDrop
    logFile.close()

if __name__ == "__main__":
    exit(main() or 0)
