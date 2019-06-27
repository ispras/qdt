from common import (
    iter_submodules,
    pypath
)

# This module uses custom version of Python Lex-Yacc
with pypath("ply"):
    for mod in iter_submodules():
        exec("from ." + mod + " import *")
