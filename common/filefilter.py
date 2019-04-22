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

    def find_files(self, rootdir):
        files = listdir(rootdir)

        for inclusive, pattern in self:
            r = compile(pattern)
            if inclusive:
                    files = list(filter(r.match, files))
            else:
                for test in list(filter(r.match, files)):
                    files.remove(test)
            if not files:
                break
        return inclusive, pattern, files
