__all__ = [
    "iter_import_lines"
  , "gen_import_code"
  , "update_this"
]

from .caller_file_name import (
    caller_file_name,
)
from .iter_submodules import (
    iter_submodules,
)
from .shadow_open import (
    shadow_open,
)

from os.path import (
    dirname,
    isdir,
    join,
    splitext,
)


def iter_import_lines(module_dir, all_submodule = None):
    for n in sorted(iter_submodules(cur_dir = module_dir)):
        if n == "this":
            continue
        modname = splitext(n)[0]
        if all_submodule:
            if all_submodule == n:
                continue
            if isdir(join(module_dir, n)):
                modname += "." + all_submodule
        yield "from ." + modname + " import *"


def gen_import_code(module_dir, **kw):
    return "\n".join(iter_import_lines(module_dir, **kw))


def update_this(**kw):
    """ It creates/updates this.py file that imports all submodules and can
be parsed by IDEs.

Use it in such a way in __init__.py:

from common import (
    update_this,
)
update_this()
from .this import *

@param all_submodule
    Name of submodule that should do `update_this(); from .this import *`
    (`__init__.py` by default).
    """

    cur_dir = dirname(caller_file_name())
    importer_name = join(cur_dir, "this.py")

    code = gen_import_code(cur_dir, **kw)

    with shadow_open(importer_name) as f:
        f.write(code)
