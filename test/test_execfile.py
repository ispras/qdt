from unittest import (
    TestCase,
    main
)
from os.path import (
    dirname,
    join
)
from common import (
    stdlog,
    execfile
)
from path import (
    Path
)
from sys import (
    modules
)


TDIR = join(dirname(__file__), "execfile_tests")


class TestExecfile(TestCase):

    def setUp(self):
        self.log = stdlog(True)

    def ex(self, filename):
        f = join(TDIR, filename)
        with self.log:
            execfile(f)
        return f

    def ex_inplace(self, filename):
        with Path(TDIR):
            with self.log:
                execfile(filename)

    def assertOut(self, expected, msg = None):
        self.assertEqual(self.log.out, expected, msg)

    def test_helloworld(self):
        self.ex("helloworld.py")

        self.assertIs(self.log.e_type, None, "An exception happened")
        self.assertOut("Hello, World!\n")

    def test_import(self):
        self.ex("import.py")
        del modules["helloworld"]

        self.assertIs(self.log.e_type, None, "An exception happened")
        self.assertOut("Hello, World!\n")

    def test_import_relfilename(self):
        self.ex_inplace("import.py")
        del modules["helloworld"]

        self.assertIs(self.log.e_type, None, "An exception happened")
        self.assertOut("Hello, World!\n")

    def test_exception(self):
        f = self.ex("exception.py")

        self.assertIs(self.log.e_type, RuntimeError)
        self.assertEqual(self.log.e_file, f, "Exception position missed")

    def test_syntax_error(self):
        f = self.ex("syntaxerror.py")

        self.assertIs(self.log.e_type, SyntaxError)
        self.assertEqual(self.log.e.lineno, 2, "Exception position missed")
        self.assertEqual(self.log.e.filename, f,
            "Exception position missed"
        )


if __name__ == "__main__":
    main()
