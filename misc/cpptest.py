from common import (
    qdtdirs,
    makedirs,
    pypath,
)
from source import (
    get_cpp_search_paths,
    iter_gcc_defines,
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


gccDefines = tuple(iter_gcc_defines())
systemCPPPaths = get_cpp_search_paths()
CPPLexer = lex(ply.cpp)
proc = Process()


def system_cpp(
    fullInPath,
    CPPPaths = tuple(),
    P = True,
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
          # no standard includes (all must be in CPPPaths)
          "-nostdinc",
        ]
      + (
            # no line markers
            ["-P"] if P else []
        )
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


class CacheStats:

    __slots__ = (
        "t_sources",
        "t_variants",
        "t_base_tokens",
        "t_ready_tokens",
    )

    def __init__(self, **kw):
        for a in self.__slots__:
            setattr(self, a, kw.get(a, 0))

    @classmethod
    def compute(cls, inc_cache):
        t_sources = 0
        t_variants = 0
        t_base_tokens = 0
        t_ready_tokens = 0

        if inc_cache:
            for i in inc_cache.values():
                t_sources += 1

                try:
                    lines = i.lines
                except AttributeError:
                    pass
                else:
                    for l in lines:
                        t_base_tokens += len(l)

                try:
                    variants = i.variants
                except AttributeError:
                    pass
                else:
                    t_variants += len(variants)
                    for v in variants:
                        t_ready_tokens += len(v.tokens)

        l = locals()
        return cls(**dict((a, l.get(a, 0)) for a in cls.__slots__))

    def __sub__(self, c):
        return CacheStats(**dict(
            (a, getattr(self, a) - getattr(c, a)) for a in self.__slots__
        ))

    def iter_lines(self):
        return ("%s = %s" % (a, getattr(self, a)) for a in self.__slots__)

    def lines(self, indent = "\t"):
        return ("\n" + indent).join(self.iter_lines())

    def __str__(self):
        return "CacheStats: " + ", ".join(self.iter_lines())


def limit_cache(inc_cache, t_ready_tokens_limit):
    ranks = []
    rank2inc = dict()
    t_ready_tokens = 0

    for i in inc_cache.values():
        try:
            variants = i.variants
        except AttributeError:
            continue

        for v in variants:
            lvtokens = len(v.tokens)
            t_ready_tokens += lvtokens
            rank = (
                -getattr(v, "usages", 0)
                -len(variants),
                lvtokens,
                id(v),  # except same keys in `rank2inc`
            )
            rank2inc[rank] = (v, i)
            ranks.append(rank)

    if t_ready_tokens <= t_ready_tokens_limit:
        return

    ranks.sort()

    while (t_ready_tokens_limit < t_ready_tokens) and ranks:
        rank = ranks.pop()
        v, i = rank2inc.pop(rank)
        t_ready_tokens -= len(v.tokens)
        i.variants.remove(v)
        if not i.variants:
            del inc_cache[i.text]


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
    arg("-P",
        action = "store_true",
        help = "do not pass -P to system cpp",
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
    arg("-n", "--normalize",
        help = "make output more comparable",
        action = "store_true",
    )
    arg("--total-ready-tokens-limit",
        help = "limit ready cached tokens of preprocessed files",
        default = "25000000",
    )

    args = ap.parse_args()

    # cache
    inDir = args.i
    pattern = args.p
    outDir = args.o
    CPPPaths = sorted(set(args.I))
    tLimit = float(args.t)
    cpp = args.cpp
    P = args.P
    normalize = args.normalize
    tReadyTokensLimit = int(args.total_ready_tokens_limit)

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
    log("no -P to system cpp:\n\t" + str(P))
    log("normalize:\n\t" + str(normalize))
    log("tLimit:\n\t" + str(tLimit))
    log("tReadyTokensLimit:\n\t" + str(tReadyTokensLimit))

    rePattern = compile(pattern)

    # cache
    matches = rePattern.match
    inDirSfxLen = len(inDir) + len(sep)
    pathSlice = slice(inDirSfxLen, None)

    tStart = time()
    total = 0

    inc_cache = None
    statsPrev = CacheStats()

    prev_spaces = set()
    # cache
    account_spaces = prev_spaces.update
    clear_spaces = prev_spaces.clear

    allIncPaths = tuple(chain(CPPPaths, systemCPPPaths))

    # Defining gcc's macros for each file confuses Preprocessor caching.
    # Instead, they are defined once and reused.
    # Note, ply.cpp.Macro objects are constants actually.
    # This also ensures __DATE__ & __TIME__ macros are same for all files.
    p = Preprocessor(CPPLexer)
    for __ in map(p.define, gccDefines): pass
    gccMacros = p.macros
    del p

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

            p = Preprocessor(CPPLexer)
            WS = p.t_WS

            makedirs(curOutDir, exist_ok = True)

            outFile = open(fullOutPath, "w")
            # cache
            write = outFile.write

            if cpp:
                try:
                    outData = system_cpp(fullInPath,
                        CPPPaths = (dirPath,) + allIncPaths,
                        P = not P,
                    )
                except:
                    outData = ""

                if normalize:
                    lex = CPPLexer.clone()
                    lex.input(outData)

                    token = lex.token

                    clear_spaces()
                    tok = token()
                    while tok:
                        if tok.type in WS:
                            account_spaces(tok.value)
                        else:
                            if prev_spaces:
                                if '\n' in prev_spaces:
                                    write('\n')
                                else:
                                    write(' ')
                                clear_spaces()

                            write(tok.value)

                        tok = token()
                else:
                    write(outData)
            else:
                inData = p.read_include_file(fullInPath)

                if inc_cache is None:
                    if hasattr(p, "inc_cache"):
                        inc_cache = p.inc_cache
                else:
                    p.inc_cache = inc_cache

                p.add_path(dirPath)
                for __ in map(p.add_path, allIncPaths): pass
                p.macros.update(gccMacros)

                p.parse(inData, fullInPath)

                # cache
                token = p.token

                clear_spaces()
                tok = token()
                if normalize:
                    while tok:
                        if tok.type in WS:
                            account_spaces(tok.value)
                        else:
                            if prev_spaces:
                                if '\n' in prev_spaces:
                                    write('\n')
                                else:
                                    write(' ')
                                clear_spaces()

                            write(tok.value)

                        tok = token()
                else:
                    while tok:
                        write(tok.value)
                        tok = token()

                statsNow = CacheStats.compute(inc_cache)
                log("stat:\n\t%s" % statsNow.lines(indent = "\t"))
                log(
                    "diff:\n\t%s" % (statsNow - statsPrev).lines(indent = "\t")
                )
                if inc_cache is not None:
                    limit_cache(inc_cache, tReadyTokensLimit)
                statsNow = CacheStats.compute(inc_cache)
                log(
            "after_limit statsNow:\n\t%s" % statsNow.lines(indent = "\t")
                )
                log(
            "diff with prev:\n\t%s" % (statsNow - statsPrev).lines(indent = "\t")
                )
                statsPrev = statsNow

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
