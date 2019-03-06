from common import (
    iter_submodules
)

for mod in iter_submodules():
    if mod.startswith("test_"):
        exec("from ." + mod + " import *")
