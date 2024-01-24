from source import *

from six.moves import (
    zip_longest,
)


def fix_indents(code, width = 38):
    chunk = SourceChunk(None, None, code)
    chunk.check_cols_fix_up(max_cols = width)
    return chunk.code


def max_width(lines):
    return max(len(l) for l in lines)


def print_code(code):
    fixed_code = fix_indents(code)

    cl, fxcl = code.splitlines(), fixed_code.splitlines()

    left_width = max_width(fxcl)

    for fxc, c in zip_longest(fxcl, cl, fillvalue = ""):
        print("%-*s | %s" % (left_width, fxc, c))


if __name__ == "__main__":
    add_base_types()

    _i = Variable("i", Type["int"])
    _a = Variable("a", Type["int"])
    _p = Pointer(Structure("Test",
        Variable("i", Structure("Test2",
            Pointer(Type["int"])("ii")
        ))
    ))("p")

    _pi = OpSDeref(_p, "i")

    root = BodyTree()(
        Declare(OpDeclareAssign(_i, 1), _a),

        Comment("It is expected to be a `do {... } while (...);`"),
        LoopDoWhile(_i)(
            OpAssign(_a, OpAdd(_i, 2))
        ),

        Comment("It is `if` *with* else block"),
        BranchIf(OpNEq(_i, CINT("0xDEAD")))(
            OpAssign(_a, CINT("0xBEEF")),
            BranchElse()(
                OpAssign(_a, CINT("0b0001011"))
            )
        ),

        Comment("It is `if` *without* else block"),
        BranchIf(OpNEq(_i, CINT("0xBAD")))(
            OpAssign(_a, CINT("0xF00D"))
        ),
        Comment("---"),

        BranchSwitch(_a,
            cases = [
                SwitchCase(1)(
                    OpAssign(_i, 123)
                )
            ]
        )(
            SwitchCase((CINT("0b010"), CINT("0b110")))(
                OpAssign(_i, 456),
            ),
            SwitchCaseDefault(
                OpAssign(_i, 789)
            )
        ),

        Comment("It is a very L " + " O " * 200 + " N  G comment"),

        OpAssign(_a, OpSub(OpMul(3, _i), 2)),
        OpAssign(_a, OpMul(3, OpSub(100, _i))),

        LoopFor(None, _i, None)(
            Break()
        ),

        LoopFor(None, None, OpInc(_i))(
            Break()
        ),

        LoopFor(None, None, OpPreInc(_i))(
            Break()
        ),

        Return(0),

        Return(),

        Call(OpSDeref(_pi, "ii")),
        Call(OpSDeref(_p, "i")),

        OpSDeref(_pi, "ii"),
        OpSDeref(_p, "i"),

        Ifdef("test1"),
        Ifdef(Macro("test2")),

        Ifdef("A")(
            OpAssign(_a, 1),
            Ifdef("B")(
                OpAssign(_a, 2)
            )
        )
    )

    print_code(str(root))

