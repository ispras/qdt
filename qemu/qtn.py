__all__ = [
    "QemuTypeName"
]

from common import (
    ee,
)
from source import (
    CIdGen,
)

QTN_DEBUG = ee("QTN_DEBUG")


class QemuTypeName(object):

    def __init__(self, name):
        self.name = name

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        result = CIdGen.generate(value, debug = QTN_DEBUG)

        self.for_id_name, \
        self.for_header_name, \
        self.for_struct_name, \
        self.for_macros, \
            = result

        self.type_macro = "TYPE_" + self.for_macros

        self._name = value
