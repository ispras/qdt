__all__ = [
    "DWARFInfoCache"
]

from .dia import (
    DWARFInfoAccelerator
)
from common import (
    intervalmap
)
from .type import (
    Type
)
from .glob import (
    Subprogram
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
