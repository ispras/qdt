from common import (
    pypath,
    update_this,
)
update_this()

# This module uses custom version of Python Lex-Yacc
with pypath("ply"):
    from .this import *
