from common import (
    iter_submodules,
    pypath
)

# this module uses custom pyelftools
with pypath("pyelftools"):
    for mod in iter_submodules():
        exec("from ." + mod + " import *")
