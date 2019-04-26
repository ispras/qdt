from unittest import (
    TestCase,
    main
)
from source import (
    CSTR,
    CINT,
    CConst
)
from common import (
    pypath,
    ee
)
with pypath("..ply"):
    from ply.lex import lex


# Defining a lexer affects `ply.yacc.LRParser.parse` invocations without
# explicit `lexer` argument value because a new lexer overwrites existing lexer
# inside `ply` (it's a global reference).
def t_ANY(t):
    ".+"
    return t

t_error = lambda _ : None

tokens = ["ANY"]
lex()


TEST_CCONST_VERBOSE = ee("TEST_CCONST_VERBOSE")


class CConstTest(object):

    if TEST_CCONST_VERBOSE:
        def setUp(self):
            print("== " + self.data + " ==")

    def test(self):
        self.parsed = CConst.parse(self.data)
        self.back = str(self.parsed)

        self.assertIsInstance(self.parsed, self.expected_type)
        self.assertEqual(self.back, self.data)

    if TEST_CCONST_VERBOSE:
        def tearDown(self):
            print(self.back, repr(self.parsed))


class AStringTest(CConstTest, TestCase):
    data = """an arbitrary
string with new line and quoted "@" and Windows\r\nnewline"""
    expected_type = CSTR


class CINTTest(CConstTest):
    expected_type = CINT


class RegularIntTest(CINTTest):
    """ `CINT` assumes decimal representation of `int` without leading zeros to
be regular. A regular CINT is assumed to be equal to a same valued `int`
ignoring the absence of an appearance information.
    """

    def test(self):
        super(RegularIntTest, self).test()

        self.assertEqual(self.parsed, self.parsed.v)


class PositiveHexTest(CINTTest, TestCase):
    data = "0x1F000"


class NegativeHexTest(CINTTest, TestCase):
    data = "-0xDEADBEEF"


class PositiveDecimalTest1(RegularIntTest, TestCase):
    data = "1"


class PositiveDecimalTest2(RegularIntTest, TestCase):
    data = "1223235324"


class NegativeDecimalTest(RegularIntTest, TestCase):
    data = "-1"


class LeadingZerosHexTest1(CINTTest, TestCase):
    data = "0x0001"


class LeadingZerosHexTest2(CINTTest, TestCase):
    data = "0x000"


class LeadingZerosBinTest1(CINTTest, TestCase):
    data = "0b01011010101"


class LeadingZerosBinTest2(CINTTest, TestCase):
    data = "0b00000"


class BinZeroTest(CINTTest, TestCase):
    data = "0b0"


class DeciamlZeroTest(RegularIntTest, TestCase):
    data = "0"


class EmptyCINTTest(TestCase):

    def test(self):
        self.assertRaises(ValueError, lambda : CINT(""))


class HexZeroTest(CINTTest, TestCase):
    data = "0x0"


class TestCINTParser(TestCase):

    def test(self):
        self.assertEqual(CINT("0"), 0)

    def test_0x18(self):
        self.assertEqual(CINT("0x18"), CINT(24, 16, 2))

    def test_0b11100111(self):
        # If difference of digits amount in two CINT does not affects
        # string form, then it is negligible.

        # Right CINT requires at least 0 digits, It does not result in leading
        # zeros. Left CINT requires 8 digits, according to original string
        # form. It has no leading zeros, apparently. So, CINTs are considered
        # equal.
        self.assertEqual(CINT("0b11100111"), CINT(231, 2, 0))
        # Right CINT has 1 leading zero, CINTs are not equal.
        self.assertNotEqual(CINT("0b11100111"), CINT(231, 2, 9))

if __name__ == "__main__":
    main()
