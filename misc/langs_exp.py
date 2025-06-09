from source import (
    CEnum,
    CExpr,
    short_ply_grammar,
    Type,
)


class Common:

    @staticmethod
    def t_WS(t):
        r"[ \t]"

    @staticmethod
    def t_NL(t):
        r"(\r\n+)|\n"
        t.lexer.lineno += 1

    @staticmethod
    def t_error(t):
        raise SyntaxError(repr(t))

    @staticmethod
    def p_error(p):
        raise SyntaxError(repr(p))


@short_ply_grammar(
    debugfile = True,
    start = "type_specifier",
)
class CEnum0(CEnum, Common):
    pass


@short_ply_grammar(
    debugfile = True,
    start = "type_specifier",
)
class CEnum1(CEnum, CExpr, Common):
    pass


res = CEnum0.parse("""
enum ETest0 { A0, B0, C0 }
""",
    debug = True,
)

print(repr(res))

res = CEnum0.parse("""
enum ETest1 { A1, B1, C1, }
""",
    debug = True,
)

print(repr(res))


res = CEnum0.parse("""
enum { A2, B2, C2, }
""",
    debug = True,
)

print(repr(res))

res = CEnum0.parse("""
enum ETest0
""",
    debug = True,
)

print(repr(res))

# For Enumeration.__init__
Type("int")

res = CEnum1.parse("""
enum ETest3 { A3 = 0, B3 = 1, C3 = 2 }
""",
    debug = True,
)

print(repr(res))

res = CEnum1.parse("""
enum ETest4 { A4 = 0, B4 = 1, C4 = 2, }
""",
    debug = True,
)

print(repr(res))


res = CEnum1.parse("""
enum { A5 = 0, B5 = 1, C5 = 2, }
""",
    debug = True,
)

print(repr(res))
