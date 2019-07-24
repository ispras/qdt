__all__ = [
    "backslash_lexer"
  , "backslash_parser"
]

from common import (
    def_tokens,
    unify_rules
)
from ply.lex import (
    lex
)
from ply.yacc import (
    yacc
)


# This language corresponds to 2-nd translation phase defined by
# 5.1.1.2 of ISO/IEC 9899:202x (~C 17)

# remove escaped new-line characters

def t_SPLICE_LINES(t):
    r"\\\n"
    t.lexer.lineno += 1
    t.lexer.columnno = 1

def t_BS(t):
    r"\\+"
    t.lexer.columnno += len(t.value)
    return t

def t_NL(t):
    r"\n+"
    t.lexer.lineno += len(t.value)
    t.lexer.columnno = 1
    return t

def t_TEXT(t):
    r"[^\\\n]+"
    t.columnno = t.lexer.columnno
    t.lexer.columnno += len(t.value)
    return t

def_tokens(globals())

def t_error(t):
    raise AssertionError("How could this happen?")

backslash_lexer = lex()

def p_empty(p):
    "source :"

def p_logical_source(p):
    "source : lines"

def p_lines(p):
    """ : line
        | lines NL line
        | lines NL
    """

def p_line(p):
    """ : TEXT
        | BS
        | line line
    """

unify_rules(globals())

p_error = t_error

backslash_parser = yacc(write_tables = False)
