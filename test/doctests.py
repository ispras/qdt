from unittest import (
    main,
)
from doctest import (
    DocTestSuite,
)
from common import (
    offsets_stream,
    line_no_stream,
    intervalmap,
    hex_stream,
)


def load_tests(loader, tests, ignore):
    tests.addTests(map(DocTestSuite, [
        offsets_stream,
        line_no_stream,
        intervalmap.__module__,
        hex_stream,
    ]))
    return tests


if __name__ == "__main__":
    main()
