__all__ = [
    "PreLoader"
]

from collections import (
    namedtuple,
)
from six import (
    BytesIO
)
# this module uses official pyelftools
from elftools.elf.relocation import (
    RelocationHandler
)

SECTION = namedtuple('SECTION', 'data data_size')


class PreLoader(object):
    """ Getting and relocating ELF sections data to load into target memory """

    def __init__(self, sections_names, elffile):
        """
        :param sections_names: is list with names of ELF sections to be loaded
            into target memory
        PreLoader expect:
            sections_names = ['.text', '.rodata', '.data', '.bss']
        :param elffile: is instance of ELFFile class
        """
        self.elffile = elffile
        self.sections = dict()

        for name in sections_names:
            section = self.elffile.get_section_by_name(name)
            self.sections[name] = SECTION(
                data = section.data() if section is not None else None,
                data_size = section.data_size if section is not None else 0
            )

        if self.elffile.header.e_type == 'ET_REL':
            self.reloc_handler = RelocationHandler(self.elffile)
        else:
            self.reloc_handler = None

    def do_relocation(self, rel, section_name, section):
        """ applies section relocation """
        stream = BytesIO()
        stream.write(section.data)

        self.reloc_handler.apply_section_relocations(stream, rel)

        self.sections.update({section_name:
            SECTION(
                data = stream.getvalue(),
                data_size = section.data_size
            )
        })

    def get_sections_data(self):
        """ returns sections data """
        if self.reloc_handler is not None:
            for section_name, section in self.sections.items():
                rel = self.elffile.get_section_by_name('.rel%s' % section_name)
                if rel is not None:
                    self.do_relocation(rel, section_name, section)

        return self.sections
