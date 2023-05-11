from common import (
    pypath,
)
from libe.common.import_all import (
    update_this,
)
update_this()

# This module uses custom version of Python Lex-Yacc
with pypath("ply"):
    from .this import *
