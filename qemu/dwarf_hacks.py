__all__ = [
    "qemu_build_dir_by_dwarf"
  , "qemu_target_dir_by_dwarf"
]

from os.path import (
    abspath,
    dirname
)
from six import (
    PY3
)
from common import (
    bsep
)


def qemu_build_dir_by_dwarf(dia):
    # Sometimes trace-root.h is included by its absolute path:
    # /path/to/build/directory/./trace-root.h
    for cu in dia.di.iter_CUs():
        for f in dia.get_CU_files(cu):
            #           v--- because of /./
            if len(f) > 2 and f[-1] == b"trace-root.h":
                break
        else:
            continue
        break
    else:
        raise RuntimeError(
            "Nothing includes trace-root.h by absolute path"
        )

    f = bsep.join(f)

    if PY3:
        # TODO: Is DWARF file name encoding always utf-8?
        f = f.decode("utf-8")

    return dirname(abspath(f))


def qemu_target_dir_by_dwarf(dwarf_info):
    # There is a convention that TCG frontend (qemu target) has
    # translate.c file in its directory.
    # Also, there is only one TCG frontend per qemu binary.
    for cu in dwarf_info.iter_CUs():
        src_file = cu.get_top_DIE().attributes["DW_AT_name"].value
        if src_file.endswith(b"translate.c"):
            break
    else:
        raise RuntimeError("No compile unit for translate.c found")

    if PY3:
        # TODO: Is DWARF file name encoding always utf-8?
        src_file = src_file.decode("utf-8")

    return dirname(abspath(src_file))
