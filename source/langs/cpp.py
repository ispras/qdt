__all__ = [
    "cpp_lexer"
  , "cpp_parser"
]

from common import (
    def_tokens,
    unify_rules,
    make_count_columns
)
from ply.lex import (
    lex
)
from ply.yacc import (
    yacc
)

# This language corresponds to 3-nd and 4-th translation phases defined by
# 5.1.1.2 of ISO/IEC 9899:202x (~C 17)

for d in ["if", "ifdef", "ifndef", "elif", "else", "endif", "include",
    "define", "undef", "line", "error", "pragma"
]:
    code = """
def t_{D}(t):
    r"\\#\\s*{d}(?=\\s)"
    t.tags = ("keyword",)
    t.lexer.columnno += len(t.value)
    return t
""".format(
        d = d,
        D = d.upper()
    )
    exec(code)

def t_DEF_ID(t):
    r"\w+(?=\()"
    t.lexer.columnno += len(t.value)
    return t

def t_ID(t):
    r"\w+"
    t.lexer.columnno += len(t.value)
    return t

# ignore comments
def t_COMMENT_ML(t):
    r"/[*](.|\n|\r)*?[*]/"
    t.lexer.lineno += t.value.count('\n')

def t_COMMENT_SL(t):
    "//.*"

def t_NL(t):
    r"\n+"
    t.lexer.lineno += len(t.value)
    t.lexer.columnno = 1
    return t

t_LPAREN = r"\("
t_RPAREN = r"\)"
t_DOTS = r"\.\.\."
t_COMMA = r","

make_count_columns(globals(), line_shift = -5)

# eats all the rest
def t_PP_TOKEN(t):
    r"[^\s]+"
    t.lexer.columnno += len(t.value)
    return t

def_tokens(globals())

# ignore whitespaces
t_ignore = " \t"

def t_error(t):
    l = t.lexer
    raise ValueError("Syntax error at %d.%d" % (l.lineno, l.columnno))

cpp_lexer = lex()

def p_preprocessing_file(p):
    ": group_opt"

def p_group_opt(p):
    """ :
        | group
    """

def p_group(p):
    """ : group_part
        | group group_part
    """

def p_group_part(p):
    """ : if_section
        | control_line
        | text_line
    """
    # | # non-directive

def p_if_section(p):
    """ : if_group ENDIF NL
        | if_group elif_groups ENDIF NL
        | if_group else_group ENDIF NL
        | if_group elif_groups else_group ENDIF NL
    """

def p_if_group(p):
    ": if_group_heading group_opt"

def p_if_group_heading(p):
    """ : IF pp_tokens NL
        | IFDEF ID NL
        | IFNDEF ID NL
    """

def p_elif_groups(p):
    """ : elif_group
        | elif_groups elif_group
    """

def p_elif_group(p):
    ": ELIF pp_tokens NL group_opt"

def p_else_group(p):
    ": ELSE NL group_opt"

def p_pp_tokens_opt(p):
    """ :
        | pp_tokens
    """

def p_pp_tokens(p):
    """ : pp_token
        | pp_tokens pp_token
    """

def p_pp_token(p):
    """ : PP_TOKEN
        | ID
        | DEF_ID
        | LPAREN
        | RPAREN
        | DOTS
        | COMMA
    """
    # Starting with DEF_ID, it's likely C language syntax error, but this is
    # preprocessor that does not care.

def p_control_line(p):
    """ : INCLUDE pp_tokens NL
        | DEFINE ID replacement_list NL
        | DEFINE DEF_ID LPAREN id_list RPAREN replacement_list NL
        | DEFINE DEF_ID LPAREN DOTS RPAREN replacement_list NL
        | DEFINE DEF_ID LPAREN id_list COMMA DOTS RPAREN replacement_list NL
        | UNDEF ID NL
        | LINE pp_tokens NL
        | ERROR pp_tokens_opt NL
        | PRAGMA pp_tokens_opt NL
        | NL
    """

def p_text_line(p):
    ": pp_tokens_opt NL"

def p_replacement_list(p):
    ": pp_tokens_opt"

def p_id_list(p):
    """ : ID
        | id_list COMMA ID
    """

unify_rules(globals())

p_error = t_error

cpp_parser = yacc(write_tables = False)