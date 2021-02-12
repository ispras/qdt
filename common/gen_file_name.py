initial__all__ = [
    "gen_similar_file_name"
]

from os.path import (
    exists,
    splitext,
)
from itertools import (
    count,
)
from re import (
    compile,
)


re_produced = compile(r".*(_\d+)$")


def gen_similar_file_name(initial, existing = set()):
    """ Given `initial` file name it returns similar name of non-existing file.

Notes.
- May return `initial`.
- Existance of directories is ignored.
- Use `existing` argument to specify files those do not actually exist in
  file system but must be considired existing.
    """

    if exists(initial) or initial in existing:
        base, ext = splitext(initial)

        # Do not extend tile with "_N" suffixes.
        mi = re_produced.match(base)
        if mi:
            base = base[:-len(mi.group(1))]

        for i in count():
            file_name = base + "_%d" % i + ext

            if exists(file_name):
                continue

            if file_name in existing:
                continue

            return file_name
    else:
        return initial
