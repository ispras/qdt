__all__ = [
    "SymTab"
]

from common import (
    pypath,
    lazy,
)

with pypath("pyelftools"):
    from elftools.elf.elffile import (
        ELFFile,
    )
    from elftools.elf.sections import (
        SymbolTableSection,
    )


class SymTab(object):

    def __init__(self, elf_file_name):
        with open(elf_file_name, "rb") as stream:
            elffile = ELFFile(stream)

            section = elffile.get_section_by_name(".symtab")
            if not section or not isinstance(section, SymbolTableSection):
                raise ValueError(
                    "No symbol table found in '%s'." % elf_file_name
                )

            symbols = {}
            for i in range(section.num_symbols()):
                sym = section.get_symbol(i)
                name = sym.name
                if not name:
                    continue
                symbols[name] = sym
            self.symbols = symbols

    def __getitem__(self, name):
        return self.symbols[name]

    @lazy
    def address_map(self):
        ret = {}
        for n, sym in self.symbols.items():
            ret[n] = sym.entry.st_value
        return ret

    def get_address(self, name):
        return self.address_map[name]
