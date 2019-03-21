__all__ = [
   "get_elffile_loading"
]

from six import (
    BytesIO
)
from elftools.elf.relocation import (
    RelocationHandler
)


def get_elffile_loading(elffile):
    """
:returns loading: list of (data, addr) tuples:
    data: segment data or section data or relocated section data
    addr: load memory address

    """
    if elffile.header.e_type != "ET_REL":
        segments = filter(
            lambda x: x.header.p_type == "PT_LOAD", elffile.iter_segments()
        )
        loading = map(lambda x: (x.data(), x.header.p_vaddr), segments)
    else:
        rel_handler = RelocationHandler(elffile)
        loading = []
        offset = 0

        # TODO: do it for these sections [".text", ".rodata", ".data"]
        sections = filter(
            lambda x: x.name in [".text"],
            elffile.iter_sections()
        )

        # loading content:
        # 1) modifying .text (.text[:n] + table)
        #   n = .text size - .rodata size - .data size
        #   table:
        #       address in .text | content
        #       _________________|__________________________________
        #       n                | address to first .rodata element
        #       n + 4            | address to second .rodata element
        #                               ...
        #       n + k            | address to final .rodata element
        #       n + k + 4        | address to first .data element
        #       n + k + 8        | address to second .data element
        #                               ...
        #       n + k + m        | address to final .data element
        # 2) .rodata:
        #       address in .rodata                | content
        #       __________________________________|_______________________
        #       address to first .rodata element  | first .rodata element
        #       address to second .rodata element | second .rodata element
        #                               ...
        #       address to final .rodata element  | final .rodata element
        # 3) .data
        #       address in .data                | content
        #       ________________________________|_____________________
        #       address to first .data element  | first .data element
        #       address to second .data element | second .data element
        #                               ...
        #       address to final .data element  | final .data element

        for section in sections:
            rel = rel_handler.find_relocations_for_section(section)
            if rel is None:
                data = section.data()
            else:
                stream = BytesIO()
                stream.write(section.data())

                rel_handler.apply_section_relocations(stream, rel)

                data = stream.getvalue()
            # TODO: modify .text section (add table)
            loading.append((data, section.header.sh_addr + offset))
            # TODO: use 'sh_offset'
            offset += section.header.sh_size
    return loading
