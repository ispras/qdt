from common import (
    LineNoStream,
    LineIndex,
)
from unittest import (
    TestCase,
    main,
)


class LineIndexTest(TestCase):

    def test(self):
        index = LineIndex()
        stream = LineNoStream(size = 2 << 20)
        index.build(stream)

        def test_read_chunk(lineno):
            chunk, start_line = index.read_chunk(stream, lineno)
            self.assertLessEqual(start_line, lineno)
            self.assertLess(lineno, start_line + index.lines_chunk)
            self.assertTrue(chunk.startswith(b"%d\r\n" % start_line))

        test_read_chunk(1000)
        test_read_chunk(100000)
        test_read_chunk(200000)


if __name__ == "__main__":
    main()
