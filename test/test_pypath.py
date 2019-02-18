from unittest import (
    TestCase,
    main
)
from common import (
    pypath
)
from cProfile import (
    runctx
)


def _import_a_module():
    with pypath(".pypath_test"):
        import a_module


class TestPyPath(TestCase):

    def test_cProfile(self):
        runctx("_import_a_module()", globals(), locals())


if __name__ == "__main__":
    main()
