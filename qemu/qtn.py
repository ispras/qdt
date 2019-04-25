__all__ = [
    "QemuTypeName"
]

from common import (
    ee,
    pypath
)
with pypath("..ply"):
    from ply.yacc import (
        yacc
    )
    from ply.lex import (
        lex
    )
from collections import (
    namedtuple as nt
)


QTN_DEBUG = ee("QTN_DEBUG")


# Different character forms are used for generation of different entities.
# I.e. name of function or variable must use lower case. A MACRO must use
# upper case. A structure must have upper camel case name.
qtnchar = nt("qtnchar", "id_char file_char struct_char macro_char")


# Lexer.
# Allowed characters.

def t_NUMBER(t):
    r"[0-9]+"
    c = t.value
    t.value = qtnchar(c, c, c, c)
    return t

def t_LOWER(t):
    r"[a-z]"
    c = t.value
    t.value = qtnchar(c, c, c, c.upper())
    return t

def t_UPPER(t):
    r"[A-Z]"
    c = t.value
    t.value = qtnchar(c.lower(), c.lower(), c, c)
    return t

# Special replacements for forbidden characters.

# Slash is just discarded.
# Ex.: "I/O" ("Input/Output") should be handled as IO, etc.
def t_SLASH(t):
    r"[/\\]"

# Replace forbidden characters with '_'.
# But `struct` name must not have `_`.
def t_FORBIDDEN(t):
    r"."
    t.value = qtnchar('_', '_', '', '_')
    return t

tokens = tuple(k[2:] for k in globals() if k[:2] == "t_")

def t_error(t):
    raise NotImplementedError(
        "You just found a bug in Qemu type name generator!"
    )


# Parser produces list of `qtnchar`s those will be used for thing
# construction.

def p_empty_or_forbidden_only(p):
    "p_stripped : prefix"
    p[0] = [qtnchar("", "", "", "")]

def p_stripped_left(p):
    "p_stripped : prefix qtn"
    # Prefix discards unused junk.
    p[0] = p[2]

def p_prefix(p):
    """ prefix :
               | prefix NUMBER
               | prefix separator
    """
    # Discard leading digits and separators.

def p_stripped_right(p):
    "p_stripped : prefix head"
    # Discard separator to the right. Note, multiple separators are discarded
    # by `head` rule.
    p[0] = p[2][:-1]

def p_qtn(p):
    "qtn : word"
    p[0] = p[1]

def p_qtn_merge(p):
    "qtn : qtn word"
    p[0] = p[1] + p[2]

def p_head(p):
    "head : qtn separator"
    p[0] = p[1] + p[2]

def p_head_2(p):
    "head : head separator"
    # Take only first separator, discard rest.
    p[0] = p[1]

def p_qtn_join_digits(p):
    "qtn : head digits"
    p[0] = p[1] + p[2]

def p_qtn_join_word(p):
    "qtn : head word"
    # Capitalize structure name.
    p[0] = p[1] + [
        p[2][0]._replace(struct_char = p[2][0].struct_char.capitalize())
    ] + p[2][1:]

def p_word(p):
    """ word : LOWER
             | UPPER
    """
    p[0] = [p[1]]

def p_word_and_digits(p):
    "word : word digits"
    p[0] = p[1] + p[2]

def p_separator(p):
    """ separator : SLASH
                  | FORBIDDEN
    """
    p[0] = [p[1]]

# numbers may be separated by an ignored token (like SLASH)
def p_digits_join(p):
    "digits : digits NUMBER"
    p[0] = p[1] + [p[2]]

def p_digits(p):
    "digits : NUMBER"
    p[0] = [p[1]]

p_error = t_error


lexer = lex()
parser = yacc()


class QemuTypeName(object):

    def __init__(self, name):
        self.name = name

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        result = parser.parse(value, lexer = lexer, debug = QTN_DEBUG)

        self.for_id_name, \
        self.for_header_name, \
        self.for_struct_name, \
        self.for_macros, \
            = map("".join, zip(*result))

        self.type_macro = "TYPE_" + self.for_macros

        self._name = value
