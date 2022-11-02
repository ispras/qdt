__all__ = [
    "iter_import_lines"
  , "gen_import_code"
  , "update_this"
]

from .pypath import (
    caller_file_name,
    iter_submodules,
)

from os.path import (
    dirname,
    exists,
    join,
    splitext,
)


def iter_import_lines(module_dir):
    for n in sorted(iter_submodules(cur_dir = module_dir)):
        if n == "this":
            continue
        yield "from ." + splitext(n)[0] + " import *"


def gen_import_code(module_dir):
    return "\n".join(iter_import_lines(module_dir))


def update_this():
    """ It creates/updates this.py file that imports all submodules and can
be parsed by IDEs.

Use it in such a way in __init__.py:

from common import (
    update_this,
)
update_this()
from .this import *
    """

    cur_dir = dirname(caller_file_name())
    importer_name = join(cur_dir, "this.py")

    code = gen_import_code(cur_dir)

    if exists(importer_name):
        with open(importer_name, "r") as f:
            generate = (f.read() != code)
    else:
        generate = True

    if generate:
        with open(importer_name, "w") as f:
            f.write(code)
