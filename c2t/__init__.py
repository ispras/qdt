from common import (
    pypath,
    iter_submodules
)

# This module uses pyrsp which import elftools. It must import our elftools.
with pypath("..debug.pyelftools"):
    for mod in iter_submodules():
        exec("from ." + mod + " import *")
