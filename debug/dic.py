__all__ = [
    "DWARFInfoCache"
]

from .dia import (
    DWARFInfoAccelerator
)
from .type import (
    Type
)


class DWARFInfoCache(DWARFInfoAccelerator):
    "Extends `DWARFInfoAccelerator` with caching of high level data."

    def __init__(self, di, symtab = None):
        super(DWARFInfoCache, self).__init__(di)

        self.symtab = symtab

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
