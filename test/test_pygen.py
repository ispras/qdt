from unittest import (
    TestCase,
    main
)
from examples import (
    Q35Project_2_6_0
)
from common import (
    PyGenerator
)
from six import (
    StringIO
)
import qdt

class TestPyGenerator(TestCase):

    def setUp(self):
        self._original = Q35Project_2_6_0()

    def test(self):
        buf = StringIO()
        self._generator = g = PyGenerator(backend = buf)
        g.serialize(self._original)
        code = buf.getvalue()
        res = {}
        exec(code, qdt.__dict__.copy(), res)
        loaded = res[self._generator.nameof(self._original)]
        self.assertEqual(loaded, self._original, "Loaded object differs.")

if __name__ == "__main__":
    main()
