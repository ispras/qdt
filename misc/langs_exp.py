from source import (
    CDeclaration,
    CDeclarationAndExpr,
    CEnum,
    CExpr,
    CStructOrUnion,
    short_ply_grammar,
    Type,
)


# TODO: int static my_func(), my_var, *my_ptr;


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
    start = "declaration",
)
class CDeclarationEx(CStructOrUnion, CEnum, CDeclarationAndExpr, Common):
    pass

res = CDeclarationEx.parse("""
typedef struct _CTypedef { void *X; } CTypedef
""",
    debug = True,
)
print(repr(res))


@short_ply_grammar(
    debugfile = True,
    start = "type_specifier",
)
class CStructOrUnion0(CStructOrUnion, CDeclaration, CExpr, Common):
    pass


# for usage in structures below
Type("long", base = True, incomplete = False)

res = CStructOrUnion0.parse("""
struct STestBitfield { long X:30; }
""",
    debug = True,
)
print(repr(res))

res = CStructOrUnion0.parse("""
struct STestBitfields { long X:30, Y:34; }
""",
    debug = True,
)
print(repr(res))

res = CStructOrUnion0.parse("""
struct STestBitfieldsManyTypes { long X:30, Y:34; long z:10; long Z:54; }
""",
    debug = True,
)
print(repr(res))

res = CStructOrUnion0.parse("""
struct STestSingle { long X; }
""",
    debug = True,
)
print(repr(res))

res = CStructOrUnion0.parse("""
struct STestCommonType { long X, Y, Z; }
""",
    debug = True,
)
print(repr(res))

res = CStructOrUnion0.parse("""
struct STestPerFieldType { long X; long Y; long Z; }
""",
    debug = True,
)
print(repr(res))

res = CStructOrUnion0.parse("""
struct STestPerFieldTypespecs { void * X; void *Y; void* Z; }
""",
    debug = True,
)
print(repr(res))

res = CStructOrUnion0.parse("""
struct STestCommonType
""",
    debug = True,
)
print(repr(res))

res = CStructOrUnion0.parse("""
struct STestTypespecsOfCommonType { void *X, *Y, *Z; }
""",
    debug = True,
)
print(repr(res))


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
