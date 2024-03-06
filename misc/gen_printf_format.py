from common import (
    callco,
    CodeWriter,
)
from source import (
    add_base_types,
    co_build_inclusions,
    Type,
    gen_printf_format,
)

from os import (
    mkdir,
    remove,
    rmdir,
)
from os.path import (
    join,
)
from tempfile import (
    mktemp,
)


def main():
    # obtain print format macros
    tmpdir = mktemp()
    tmph = join(tmpdir, "tmp.h")
    mkdir(tmpdir)

    try:
        with open(tmph, "w") as h:
            h.write("#include<inttypes.h>\n")

        try:
            callco(co_build_inclusions(
                tmpdir,
                [
                    (".", False),
                ]
            ))
        finally:
            remove(tmph)
    finally:
        rmdir(tmpdir)

    add_base_types()


    for t, settings in (
        (Type["int8_t"], dict(width = True)),
        (Type["uint16_t"], dict(width = True)),
        (Type["uint32_t"], dict(width = True)),
        (Type["uint64_t"], dict(width = True)),
        (Type["uint32_t"], dict()),
        (Type["uint32_t"], dict(width = 15)),
        (Type["uint32_t"], dict(base = 16, width = True)),
        (Type["uint64_t"], dict(base = 16)),
        (Type["uint64_t"], dict(
            base = 16,
            width = True,
            leading = "0"))
        ,
    ):
        cw = CodeWriter()
        gen_printf_format(t, **settings).__c__(cw)
        print(cw.w.getvalue())


if __name__ == "__main__":
    exit(main() or 0)
