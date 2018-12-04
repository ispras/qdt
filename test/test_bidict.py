from unittest import (
    TestCase,
    main
)
from common import (
    bidict
)


class BiDictTest(TestCase):

    def test(self):
        fwd = bidict(a = 0)
        bwd = fwd.mirror

        self.assertIs(fwd, bwd.mirror)
        self.assertIs(bwd, fwd.mirror)

        self.assertEqual(fwd["a"], 0)
        self.assertEqual(bwd[0], "a")

        fwd["b"] = 1
        self.assertEqual(bwd[1], "b")

        del bwd[0]
        self.assertNotIn("a", fwd)

        del bwd[1]
        self.assertNotIn("b", fwd)

        bwd[2] = "c"
        self.assertEqual(fwd["c"], 2)

        fwd.update(d = 3, e = 4)
        self.assertEqual(bwd[3], "d")
        self.assertEqual(bwd[4], "e")

        bwd.update({5 : "f", 6: "g"})
        self.assertEqual(fwd["f"], 5)
        self.assertEqual(fwd["g"], 6)

        bwd.setdefault(7, "h")
        self.assertEqual(fwd["h"], 7)

        self.assertEqual(fwd.key(2), "c")
        self.assertEqual(fwd.key(8, "i"), "i")

        self.assertEqual(fwd.pop("d"), 3)
        self.assertNotIn(3, bwd)
        self.assertEqual(fwd.pop("d", 0xbadf00d), 0xbadf00d)

        self.assertEqual(bwd.pop(5), "f")
        self.assertNotIn("f", fwd)

        self.assertRaises(TypeError, lambda : bwd.pop(5, "junk", "junk"))
        self.assertRaises(KeyError, lambda : bwd.pop(5))


if __name__ == "__main__":
    main()
