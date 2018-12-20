__all__ = [
    "str2c"
]

from common import (
    gen_tokens
)
import common.ply2path
from ply.lex import lex

# escape @ (for C boilerplate generator)
def t_C_GEN_ESCAPE(t):
    "@"
    t.value = "@@"
    return t

# space inside a C string should not be breaked during auto line wrapping
def t_SPACE(t):
    "[ ]"
    t.value = "@b"
    return t

# escape quotes (C grammar)
def t_QUOTES(t):
    '"'
    t.value = '\\"'
    return t

# split string onto two parts and add safe breaking space between
def t_WINDOWS_NEWLINE(t):
    r"\r\n"
    t.value = r'\\r\\n"@s"'
    return t

def t_MAC_NEWLINE(t):
    r"\r"
    t.value = r'\\r"@s"'
    return t

def t_LINUX_NEWLINE(t):
    r"\n"
    t.value = r'\\n"@s"'
    return t


def t_CHARACTER(t):
    "."
    return t

def t_error(t):
    raise AssertionError("All characters are valid for this lexer!")

# Define tokens
tokens = tuple(gen_tokens(globals()))

# Build lexer
lexer = lex()

def str2c(s):
    "Adapts a Python string for both C language and QDT boilerplate generator"
    lexer.input(s)
    return '"' + "".join(t.value for t in lexer) + '"'
