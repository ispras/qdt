__all__ = [
    "iter_import_lines"
  , "gen_import_code"
  , "update_this"
]

from libe.common.caller_file_name import (
    caller_file_name,
)
from libe.common.iter_submodules import (
    iter_submodules,
)
from .shadow_open import (
    shadow_open,
)

from os.path import (
    dirname,
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

    with shadow_open(importer_name) as f:
        f.write(code)
