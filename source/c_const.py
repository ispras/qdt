__all__ = [
    "CConst"
      , "CINT"
      , "CSTR"
]

if __name__ == "__main__":
    from c_str_adapter import str2c
else:
    from .c_str_adapter import str2c

from string import (
    digits,
    ascii_uppercase
)

class CConst(object):
    @staticmethod
    def parse(s):
        try:
            return parser.parse(s)
        except (QCParserError, QCLexerError):
            return CSTR(s)

    def gen_c_code(self):
        "Implementation must return string compatible with C generator"
        raise NotImplementedError()

    def __c__(self, writer):
        writer.write(self.gen_c_code())

    def __ne__(self, v):
        "Explicit redirection for Py2."
        return not self.__eq__(v)

digs = digits + ascii_uppercase

def uint2base(x, base):
    """Based on:
https://stackoverflow.com/questions/2267362/how-to-convert-an-integer-in-any-base-to-a-string
https://stackoverflow.com/questions/9561432/what-is-the-equivalence-in-python-3-of-letters-in-python-2
    """
    if x == 0:
        return digs[0]

    digits = []

    while x:
        digits.append(digs[x % base])
        x //= base

    digits.reverse()

    return "".join(digits)

int_prefixes = {
    2  : "0b",
    16 : "0x",
    10 : ""
}

class CINT(CConst):
    def __init__(self, value, base = 10, digits = 0):
        self.b, self.d = base, digits
        self.set(value)

    def set(self, value):
        if value is None:
            raise ValueError("There is no integer equivalent for None in C")

        if isinstance(value, int):
            self.v = value
        elif isinstance(value, str):
            try:
                new = parser.parse(value)
            except (QCParserError, QCLexerError):
                # an integer may be given by a macro
                self.v = value
            else:
                if not isinstance(new, CINT):
                    raise ValueError("The string encodes %s instead of %s" % (
                        type(new).__name__, type(self).__name__
                    ))

                self.v, self.b, self.d = new.v, new.b, new.d
        elif isinstance(value, CSTR):
            self.set(value.v)
        elif isinstance(value, CINT):
            self.v, self.b, self.d = value.v, value.b, value.d
        else:
            raise ValueError(
                "Cannot assign value of type %s" % type(value).__name__
            )

    def gen_c_code(self):
        val = self.v

        if isinstance(val, str):
            # assuming that the value is a macro
            return val

        base = self.b
        try:
            prefix = int_prefixes[base]
        except KeyError:
            # It`s a C comment
            prefix = "/* %d base */" % base

        if val < 0:
            prefix = "-" + prefix
            val = -val

        val_str = uint2base(val, base)

        return prefix + "0" * max(0, self.d - len(val_str)) + val_str

    def __repr__(self):
        return "CINT(%s, %d, %d)" % (repr(self.v), self.b, self.d)

    __str__ = gen_c_code

    __hash__ = CConst.__hash__
    def __eq__(self, v):
        if isinstance(v, CINT):
            return (self.v, self.b, self.d) == (v.v, v.b, v.d)
        elif isinstance(v, int):
            if self.d == 0 and self.b == 10:
                return self.v == v
            # else:
                # `int` does not have appearance information. So, if this CINT
                # has non-default settings, it is assumed to be not equal.
                # Fall to `return` False.
        elif isinstance(v, str):
            # Reminder that an integer can be given by a macro.
            return self.v == v

        # Some other type
        return False


class CSTR(CConst):
    def __init__(self, value):
        # C representation is computed on demand and cached
        self.v = None
        self.c = "NULL"
        self.set(value)

    def gen_c_code(self):
        c = self.c
        if c is None:
            v = self.v
            if v is None:
                c = "NULL"
            else:
                c = str2c(v)
            self.c = c
        return c

    def set(self, value):
        if isinstance(value, CConst):
            value = str(value)

        old = self.v
        if old == value:
            return

        self.c = None # reset C value cache
        self.v = value

    def __str__(self):
        return self.v

    def __repr__(self):
        return "CSTR(%s)" % repr(self.v)

    __hash__ = CConst.__hash__
    def __eq__(self, v):
        if isinstance(v, str):
            # There is no difference in target representation
            # TODO: account macros possibility (must not be enclosed with '"')
            return self.gen_c_code() == '"' + v + '"'
        elif isinstance(v, CSTR):
            return self.v == v.v
        return False


class QCLexerError(ValueError): pass
QCParserError = QCLexerError

# PLY is used to parse C constants
from common.ply2path import gen_tokens
from ply.lex import lex
from ply.yacc import yacc

def t_error(t):
    raise QCLexerError()

def p_error(p):
    raise QCParserError()

t_MINUS = "-"

def t_HEX_PREFIX(t):
    "0x"
    t.value = 16
    return t

def t_BIN_PREFIX(t):
    "0b"
    t.value = 2
    return t

def t_LEADING_ZEROS(t):
    "[0]+"
    t.value = len(t.value)
    return t

def t_BIN(t):
    "1[01]+$"
    return t

def t_DEC(t):
    "[1-9][0-9]*$"
    return t

def t_HEX(t):
    "[1-9a-fA-F][0-9a-fA-F]*$"
    return t

def p_qconst(p):
    """qconst : negative
              | uint"""
    p[0] = p[1]

def p_int(p):
    "negative : MINUS uint"
    i = p[2]
    i.v = -i.v
    p[0] = i

# Numbers
#        p - prefixed
# first  0 - leading zeros
# second 0 - zero with leading zeros
#        d - digits
def p_p0d(p):
    """uint : HEX_PREFIX LEADING_ZEROS hex
            | BIN_PREFIX LEADING_ZEROS BIN"""
    p[0] = CINT(int(p[3], base = p[1]), p[1], p[2] + len(p[3]))

def p_p00(p):
    """uint : HEX_PREFIX LEADING_ZEROS
            | BIN_PREFIX LEADING_ZEROS"""
    p[0] = CINT(0, p[1], p[2])

def p_pd(p):
    """uint : HEX_PREFIX hex
            | BIN_PREFIX BIN"""
    p[0] = CINT(int(p[2], base = p[1]), p[1])

def p_0d(p):
    "uint : LEADING_ZEROS dec"
    p[0] = CINT(int(p[2]), 10, p[1] + len(p[2]))

def p_00(p):
    "uint : LEADING_ZEROS"
    p[0] = CINT(0, 10, p[1])

def p_d(p):
    "uint : dec"
    p[0] = CINT(int(p[1]))

def p_digits(p):
    """dec : BIN
           | DEC
       hex : dec
           | HEX"""
    p[0] = p[1]

# Define tokens
tokens = tuple(gen_tokens(globals()))

# Build lexer and parser
lexer = lex()
parser = yacc()

if __name__ == "__main__":
    print(tokens)

    for data, expected in [
        ("0x1F000", CINT),
        ('''an arbitrary
string with new line and quoted "@" and Windows\r\nnewline''', CSTR),
        ("-1", CINT),
        ("1", CINT),
        ("0x0001", CINT),
        ("0b01011010101", CINT),
        ("1223235324", CINT),
        ("0b00000", CINT),
        ("0", CINT),
        ("0x000", CINT),
        ("0b0", CINT),
        ("0x0", CINT),
        ("-0xDEADBEEF", CINT)
    ]:
        print("== " + data + " ==")
        q = CConst.parse(data)
        if type(q) is not expected:
            raise AssertionError("%s / %s" % (type(q), expected))
        res = str(q)
        print(res, repr(q))
        print(q.gen_c_code())
        assert res == data
