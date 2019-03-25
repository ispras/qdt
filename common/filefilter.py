__all__ = [
    "filefilter"
]

from os import (
    listdir
)
from re import (
    compile
)


class filefilter(list):
    "A list of regexps for file selection in both inclusive and exclusive way."

    RE_INCLD = True
    RE_EXCLD = False

    def find_tests(self, rootdir):
        tests = listdir(rootdir)

        for inclusive, pattern in self:
            r = compile(pattern)
            if inclusive:
                    tests = filter(r.match, tests)
            else:
                for test in filter(r.match, tests):
                    tests.remove(test)
            if not tests:
                break
        return inclusive, pattern, tests
