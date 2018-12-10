from os import (
    environ
)
from unittest import (
    TestCase,
    main
)
from examples import (
    Q35Project_2_6_0
)
from common import (
    same,
    PyGenVisitor
)
from traceback import (
    format_exc
)
import qdt

PYGEN_VERBOSE = environ.get("PYGEN_VERBOSE", False)


class PyGeneratorTestHelper(object):

    def test(self):
        self._generator = gen = PyGenVisitor(self._original).visit().gen
        buf = gen.w
        code = buf.getvalue()
        res = {}
        try:
            exec(code, self._namespace, res)
        except:
            print("\nError in generated code:\n" + format_exc())
            eq = False
        else:
            try:
                loaded = res[self._generator.nameof(self._original)]
                eq = same(loaded, self._original)
            except:
                print("\nLoaded object is bad:\n" + format_exc())
                eq = False

        if PYGEN_VERBOSE or not eq:
            # save serialized code to the file for developer
            with open(type(self).__name__ + "__code.py", "w") as f:
                f.write(code)

        self.assertTrue(eq, "Loaded object differs.")


class TestDict(TestCase, PyGeneratorTestHelper):

    def setUp(self):
        self._namespace = {}
        self._original = {}


class TestQ35(TestCase, PyGeneratorTestHelper):

    def setUp(self):
        self._namespace = dict(qdt.__dict__)
        self._original = Q35Project_2_6_0()


if __name__ == "__main__":
    main()
