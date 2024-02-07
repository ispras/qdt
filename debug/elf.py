# Utility code for pyelftools's ELF file

__all__ = [
    "InMemoryELFFile"
  , "create_dwarf_cache"
]

from .dic import (
    DWARFInfoCache,
)

from elftools.elf.elffile import (
    ELFFile
)
from six import (
    BytesIO,
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
        self._file_name = file_name

    def create_dwarf_cache(self):
        if not self.has_dwarf_info():
            raise ValueError(
    "%s does not have DWARF info. Provide a debug build\n" % (self._file_name)
            )

        di = self.get_dwarf_info()

        if not di.debug_pubnames_sec:
            print("%s does not contain .debug_pubtypes section. Provide"
                " -gpubnames flag to the compiler" % self._file_name
            )

        return DWARFInfoCache(di,
            symtab = self.get_section_by_name(".symtab")
        )


def create_dwarf_cache(exec_file):
    return InMemoryELFFile(exec_file).create_dwarf_cache()
