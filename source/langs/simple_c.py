__all__ = [
    "simple_c_lexer"
  , "simple_c_parser"
]

from common import (
    def_tokens,
    unify_rules,
)
from ply.lex import (
    lex
)
from ply.yacc import (
    yacc
)


def t_STATIC(t):
    "static"
    return t

def t_INLINE(t):
    "inline"
    return t

def t_EXTERN(t):
    "extern"
    return t

def t_CONST(t):
    "const"
    return t

def t_ID(t):
    "[\\w_][\w\\d_]*"
    return t

def t_ARGS_BEGIN(t):
    "[(]"
    return t

def t_ARGS_END(t):
    "[)]"
    return t

def t_SEMICOLON(t):
    ";"
    return t

def t_COMMA(t):
    ","
    return t

def t_STAR(t):
    "[*]"
    return t

def t_SPACE(t):
    "\\s+"
    # ignore

def t_BLOCK_BEGIN(t):
    "{[^{}]*"
    return t

def t_BLOCK_END(t):
    "[^}]*}"
    return t

def_tokens(globals())

def t_error(t):
    raise ValueError("Unexpected character in ctags: " + repr(t.value[0]))

simple_c_lexer = lex()

def p_file(p):
    """ :
        | entities
    """
    return p

def p_entities(p):
    """ : entity
        | entities entity
    """
    return p

def p_entity(p):
    """ : function
        | function_decl
    """
    return p

def p_function(p):
    """ : opt_keywords type ID argspec block
    """
    return p

def p_function_decl(p):
    """ : opt_keywords type ID argspec SEMICOLON
    """
    return p

def p_opt_keywords(p):
    """ :
        | keywords
    """
    return p

def p_keywords(p):
    """ : keyword
        | keywords keyword
    """
    return p

def p_keyword(p):
    """ : STATIC
        | INLINE
        | EXTERN
    """
    return p

def p_type(p):
    """ : pointer
        | ID
        | CONST type
    """
    return p

def p_pointer(p):
    """ : type STAR
    """
    return p

def p_argspec(p):
    ": ARGS_BEGIN opt_args ARGS_END"
    return p

def p_opt_args(p):
    """ :
        | args
    """
    return p

def p_args(p):
    """ : arg
        | args COMMA args
    """
    return p

def p_arg(p):
    """ : type ID
    """
    return p

def p_block(p):
    """ : BLOCK_BEGIN opt_block_body BLOCK_END
    """
    return p

def p_opt_block_body(p):
    """ :
        | block_body
    """
    return p

def p_block_body(p):
    """ : block_body block_body
        | block_token
        | block
    """
    return p

def p_block_token(p):
    """ : STATIC
        | CONST
        | ID
        | ARGS_BEGIN
        | ARGS_END
        | SEMICOLON
        | COMMA
        | STAR
    """
    return p

unify_rules(globals())

def p_error(p):
    raise ValueError("Unknown C syntax")

simple_c_parser = yacc(
    write_tables = False,
    tabmodule = "simple_c_tab"
)
