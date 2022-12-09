__all__ = [
    "system_verilog_grammar",
    "system_verilog_parser",
]

from lark import (
    Lark,
)
from os.path import (
    dirname,
    join,
)


with open(join(dirname(__file__), "system_verilog.lark")) as f:
    grammar = f.read()

parser = Lark(grammar, start = "source_text", lexer = "basic")

system_verilog_parser = parser
system_verilog_grammar = grammar
