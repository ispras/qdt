__all__ = [
    "iter_submodules"
]

from .caller_file_name import (
    caller_file_name,
)

from os import (
    listdir,
)
from os.path import (
    dirname,
    isdir,
    isfile,
    join,
)


def iter_submodules(cur_dir = None):
    if cur_dir is None:
        cur_dir = dirname(caller_file_name())

    for item in listdir(cur_dir):
        if item[-3:] == ".py":
            name = item[:-3]
            if name != "__init__":
                yield name
        else:
            fullname = join(cur_dir, item)

            if isdir(fullname) and isfile(join(fullname, "__init__.py")):
                yield item
