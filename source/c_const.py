__all__ = [
    "CConst"
      , "CINT"
      , "CSTR"
]

if __name__ == "__main__":
    from c_str_adapter import str2c
else:
    from .c_str_adapter import str2c

from math import (
    log
)
from string import (
    digits,
    ascii_uppercase
)
from common import (
    pypath,
    def_tokens
)
from six import (
    integer_types
)
# PLY is used to parse C constants
with pypath("..ply"):
    from ply.lex import lex
    from ply.yacc import yacc

class CConst(object):
    @staticmethod
    def parse(s):
        try:
            return parser.parse(s, lexer = lexer)
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
        """
:param digits:
    Minimum amount of digits in the number. Prefixes like "0x" and "0b" and
    "-" (negative sign) are not accounted.
        """
        self.b, self.d = base, digits
        self.set(value)

    def set(self, value):
        if value is None:
            raise ValueError("There is no integer equivalent for None in C")

        if isinstance(value, integer_types):
            self.v = value
        elif isinstance(value, str):
            if value == "":
                raise ValueError("No integer can be an empty string")
            try:
                new = parser.parse(value, lexer = lexer)
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
        val = self.v

        if isinstance(val, str):
            # assuming that the value is a macro
            val_s = '"%s"' % val
        else:
            # Use the same form of integer constant as defined by `b`ase and
            # `d`igits.
            base = self.b
            try:
                prefix = int_prefixes[base]
            except KeyError:
                # A non-regular base, using standard form for integer
                val_s = repr(val)
            else:
                if val < 0:
                    prefix = "-" + prefix
                    val = -val

                val_s0 = uint2base(val, base)

                val_s = prefix + "0" * max(0, self.d - len(val_s0)) + val_s0

        return "CINT(%s, %d, %d)" % (val_s, self.b, self.d)

    __str__ = gen_c_code

    __hash__ = CConst.__hash__
    def __eq__(self, o):
        v, b, d = self.v, self.b, self.d
        if isinstance(o, CINT):
            if (v, b) != (o.v, o.b):
                return False

            if isinstance(v, str):
                # value is a macro, digits amount is not significant
                return True

            # digits amount are equal iff both resulting in the same string
            # from of number.
            min_digits = self.min_digits
            if min_digits < d:
                # There is at least one leading zero, amount of leading zeros
                # must be equal
                return d == o.d
            else:
                # self has no leading zeros, the other must too
                return o.d <= min_digits
        elif isinstance(o, int):
            if d <= len(str(abs(o))) and b == 10:
                return v == o
            # else:
                # `int` does not have appearance information. So, if this CINT
                # has non-default settings, it is assumed to be not equal.
                # Fall to `return` False.
        elif isinstance(o, str):
            # Reminder that an integer can be given by a macro.
            return v == o

        # Some other type
        return False

    @property
    def min_digits(self):
        v = self.v
        if v:
            if isinstance(v, str):
                raise RuntimeError(
                    "No minimum digits count is defined for a macro"
                )
            if v < 0:
                # Note that sign is *not* accounted in minimum digits count.
                v = -v
            try:
                return int(log(v, self.b)) + 1
            except ValueError: # math domain error
                print("v = %s, base = %s" % (v, self.b))
                raise
        else:
            # log(0) is a math error. Zero requires 1 digit to display.
            return 1


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
    p[0] = CINT(int(p[2], base = p[1]), p[1], len(p[2]))

def p_0d(p):
    "uint : LEADING_ZEROS dec"
    p[0] = CINT(int(p[2]), 10, p[1] + len(p[2]))

def p_00(p):
    "uint : LEADING_ZEROS"
    p[0] = CINT(0, 10, p[1])

def p_d(p):
    "uint : dec"
    p[0] = CINT(int(p[1]), digits = len(p[1]))

def p_digits(p):
    """dec : BIN
           | DEC
       hex : dec
           | HEX"""
    p[0] = p[1]

def_tokens(globals())

# Build lexer and parser
lexer = lex()
parser = yacc()
