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

from sys import (
    version_info
)
if version_info[0] == 3:
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


def create_dwarf_cache(exec_file):
    elf = InMemoryELFFile(exec_file)
    if not elf.has_dwarf_info():
        raise ValueError(
"%s does not have DWARF info. Provide a debug build\n" % (exec_file)
        )

    di = elf.get_dwarf_info()

    if not di.debug_pubnames_sec:
        print("%s does not contain .debug_pubtypes section. Provide"
            " -gpubnames flag to the compiler" % exec_file
        )

    return DWARFInfoCache(di,
        symtab = elf.get_section_by_name(".symtab")
    )
