__all__ = [
    "system_verilog_preproc_grammar",
    "system_verilog_preproc_parser",
]

from lark import (
    Lark,
)
from os.path import (
    dirname,
    join,
)


with open(join(dirname(__file__), "system_verilog_preproc.lark")) as f:
    grammar = f.read()

parser = Lark(grammar, start = "source_text", lexer = "basic")

system_verilog_preproc_grammar = grammar
system_verilog_preproc_parser = parser
