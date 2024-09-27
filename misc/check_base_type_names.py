from source import (
    iter_base_complet_type_names,
)

from itertools import (
    count,
)
from subprocess import (
    PIPE,
    Popen,
)

if __name__ == "__main__":
    already = set()

    lines = []
    line = lines.append
    line("void main()")
    line("{")
    ctr = count()
    for n in iter_base_complet_type_names():
        if n in already:
            print("duplicate: " + n)
        already.add(n)
        line("\t%s v%d;" % (n, next(ctr)))
    line("}")
    line("")

    code = "\n".join(lines)

    print("Compilling code...\n%s\n\n" % code)

    gcc = Popen(
        [
            "gcc",
            "-o", "/dev/null",
            "-x", "c",
            "-"
        ],
        stdin = PIPE,
    )

    gcc.communicate(code.encode("charmap"))
    gcc.wait()
