__all__ = [
    "DWARFInfoCache"
]

from .dia import (
    DWARFInfoAccelerator
)


class DWARFInfoCache(DWARFInfoAccelerator):
    "Extends `DWARFInfoAccelerator` with caching of high level data."

    def __init__(self, di, symtab = None):
        super(DWARFInfoCache, self).__init__(di)

        self.symtab = symtab
