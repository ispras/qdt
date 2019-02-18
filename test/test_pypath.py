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


class TestPyPath(TestCase):

    def test_cProfile(self):
        runctx("""
with pypath(".pypath_test"):
    import a_module
        """, globals(), locals()
        )


if __name__ == "__main__":
    main()
