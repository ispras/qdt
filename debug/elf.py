# Utility code for pyelftools's ELF file

__all__ = [
    "InMemoryELFFile"
]

import sys
from os.path import (
    join,
    split
)

# this package uses custom pyelftools
prev_path = list(sys.path)
sys.path.insert(0, join(split(__file__)[0], "pyelftools"))

from elftools.elf.elffile import (
    ELFFile
)

sys.path = prev_path

if sys.version_info[0] == 3:
    from io import (
        BytesIO
    )
else:
    from cStringIO import (
        StringIO as BytesIO
    )


class InMemoryELFFile(ELFFile):
    """ Like pyelftools's `ELFFile` but caches all the file in memory.
    """

    def __init__(self, file_name):
        stream = BytesIO()

        with open(file_name, "rb") as f:
            while True:
                chunk = f.read(1 << 20)
                l = len(chunk)
                if l > 0:
                    stream.write(chunk)
                if l < (1 << 20):
                    break

        super(InMemoryELFFile, self).__init__(stream)
