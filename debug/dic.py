__all__ = [
    "DWARFInfoCache"
  , "create_dwarf_cache"
]

from .dia import (
    DWARFInfoAccelerator
)
from common import (
    bstr,
    lazy,
    intervalmap
)
from collections import (
    defaultdict
)
from .type import (
    TYPE_TAGS,
    Type
)
from .glob import (
    Datum,
    Subprogram
)
from .elf import (
    InMemoryELFFile
)
from sys import (
    stderr
)


class DWARFInfoCache(DWARFInfoAccelerator):
    "Extends `DWARFInfoAccelerator` with caching of high level data."

    def __init__(self, di, symtab = None):
        super(DWARFInfoCache, self).__init__(di)

        self.symtab = symtab

        # Mapping of subprogram names to lists of `Subprogram` descriptors.
        self.subprograms = {}

        # Mapping of target addresses to subprograms covering them.
        self.addr2subprog = intervalmap()

        # cache for parsed types, keyed by names
        self.types = {}

        # cache for parsed types, keyed by DIE offsets
        self.die_off2type = {}

        # A compile unit may contain global variables. This is 2-level cache.
        # 1. CU offset -> dict of globals
        # 2. name of a global variable -> `Datum`
        self.cu_off2globals = defaultdict(dict)

    def get_CU_global_variables(self, cu):
        off = cu.cu_offset
        globs = self.cu_off2globals[off]

        if globs: # already accounted
            return globs

        for die in cu.get_top_DIE().iter_children():
            if die.tag != "DW_TAG_variable":
                continue

            var = Datum(self, die)
            globs[var.name] = var

        return globs

    def type_by_die(self, die):
        do2t = self.die_off2type

        offset = die.offset

        if offset in do2t:
            return do2t[offset]

        t = Type(self, die)

        if not t.declaration:
            # Do not add declarations to name mapping as they do not have much
            # information.
            self.types[t.name] = t

        do2t[offset] = t

        return t

    def __getitem__(self, name):
        sps = self.subprograms

        bname = bstr(name)

        if bname in sps:
            return sps[bname]

        types = self.types
        if bname in types:
            return types[bname]

        di = self.di

        # First, search in .debug_pubnames
        pubnames = self.pubnames
        if pubnames is None:
            offsets = None
        else:
            offsets = pubnames[name]

        # Second, search in .debug_pubtypes
        if offsets is None:
            pubtypes = self.pubtypes
            if pubtypes is None:
                offsets = None
            else:
                offsets = pubtypes[name]

        # Third, search in .symtab
        if offsets is None:
            symtab = self.symtab
            if symtab is None:
                raise KeyError(name)

            # Note that `bname` is not required there, `get_symbol_by_name`
            # can work with strings under both Py2 and Py3.
            symbols = symtab.get_symbol_by_name(name)
            if symbols is None:
                raise KeyError(name)

            for symbol in symbols:
                # Get CU that covers target address of current symbol
                address = symbol.entry.st_value
                cu = self.cu(address)

                # Search for a DIE with requested name
                # TODO: Only topmost DIEs are processed now. Is there a reason
                # for a deeper search?
                for die in cu.get_top_DIE().iter_children():
                    attrs = die.attributes
                    if "DW_AT_name" not in attrs:
                        continue
                    if attrs["DW_AT_name"].value == bname:
                        break
                else:
                    # No DIE with such name found in current CU
                    continue
                # A DIE with such name was found
                break
            else:
                # No DIE was found for each symbol with requested name
                raise KeyError(name)
            # Note that last cu and die variable definitions are looked for
        else:
            cu = di._parse_CU_at_offset(offsets[0])
            die = cu.get_DIE_at_offset(offsets[1] - offsets[0])

        tag = die.tag[7:] # DW_TAG_*

        if tag == "subprogram":
            sym_name = die.attributes["DW_AT_name"].value
            symbol = Subprogram(self, die, name = sym_name)
            sps[sym_name] = [symbol]
        elif tag in TYPE_TAGS:
            symbol = self.type_by_die(die)
        else:
            raise NotImplementedError("Handling name '%s' of DIE tag"
                " 'DW_TAG_%s' is not implemented yet" % (name, tag)
            )

        return symbol

    def account_all_subprograms(self):
        "Note that it may consume too many time on a large DWARF."
        for cu in self.iter_CUs():
            self.account_subprograms(cu)

    def subprogram(self, addr):
        """
    :param addr:
        is a target's one
    :returns:
        the `Subprogram` that covers given `addr`ess or `None` if no subprogram
        found for the `addr`ess.

        """

        a2s = self.addr2subprog
        sp = a2s[addr]

        if sp is None:
            cu_for_addr = self.cu(addr)
            self.account_subprograms(cu_for_addr)

            # `account_subprograms` was filled `addr2subprog` with subprograms
            # of the compilation unit. Try to look for the subprogram again.
            sp = a2s[addr]

        return sp

    def account_subprograms(self, cu):
        """  Extend `subprograms` mapping with subprograms from the compilation
unit (`cu`). Adds address intervals of subprograms to `addr2subprog` mapping.

    :param cu:
        a Compilation Unit descriptor
    :returns:
        list of subprograms in the `cu`

        """
        root = cu.get_top_DIE()
        sps = self.subprograms
        a2s = self.addr2subprog
        cu_sps = []

        for die in root.iter_children():
            if die.tag != "DW_TAG_subprogram":
                continue

            name = die.attributes["DW_AT_name"].value

            if name in sps:
                progs = sps[name]
            else:
                sps[name] = progs = []

            for sp in progs:
                if sp.die is die:
                    # The subprogram name is already accounted by __getitem__.
                    # Only ranges must be accounted in `addr2subprog`.
                    break
            else:
                sp = Subprogram(self, die, name = name)
                progs.append(sp)

            ranges = sp.ranges
            if ranges:
                for start, end in ranges:
                    a2s[start:end] = sp

            cu_sps.append(sp)

        return cu_sps

    @lazy
    def pubnames(self):
        return self.di.get_pubnames()

    @lazy
    def pubtypes(self):
        return self.di.get_pubtypes()

def create_dwarf_cache(exec_file):
    elf = InMemoryELFFile(exec_file)
    if not elf.has_dwarf_info():
        stderr("%s does not have DWARF info. Provide a debug build\n" % (
            exec_file
        ))
        return -1

    di = elf.get_dwarf_info()

    if not di.debug_pubnames_sec:
        print("%s does not contain .debug_pubtypes section. Provide"
            " -gpubnames flag to the compiler" % exec_file
        )

    return DWARFInfoCache(di,
        symtab = elf.get_section_by_name(".symtab")
    )
