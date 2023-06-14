from common import (
    hex_stream,
    intervalmap,
    line_no_stream,
    offsets_stream,
)
from libe.common import (
    attr_change_notifier,
)

from doctest import (
    DocTestSuite,
)
from unittest import (
    main,
)


def load_tests(loader, tests, ignore):
    tests.addTests(map(DocTestSuite, [
        offsets_stream,
        line_no_stream,
        intervalmap.__module__,
        hex_stream,
        attr_change_notifier,
    ]))
    return tests


if __name__ == "__main__":
    main()
