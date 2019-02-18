from unittest import (
    TestCase,
    main
)
from common import (
    pypath
)
from cProfile import (
    run
)


class TestPyPath(TestCase):

    def test_cProfile(self):
        run("""
with pypath(".pypath_test"):
    import a_module
        """)


if __name__ == "__main__":
    main()
