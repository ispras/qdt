__all__ = [
    "QRSP"

  # byte order constants
  , "BIG"
  , "LITTLE"
]

from common import (
    pypath,
)
from six import (
    add_metaclass,
)
with pypath("..pyrsp"):
    from pyrsp.rsp import (
        RSP,
        archmap
    )


class QRSPType(type):

    def __init__(self, name, *a, **kw):
        super(QRSPType, self).__init__(name, *a, **kw)

        arch = self.__arch__ or name.lower()
        archmap[arch] = self


LITTLE = True
BIG = False

@add_metaclass(QRSPType)
class QRSP(RSP):

    __arch__ = None
    __pc__ = "pc"
    __sp__ = "sp"
    __regs__ = (__pc__,) + tuple(map("r%u".__mod__, range(16)))
    __endian__ = LITTLE
    __bitsize__ = 32
    call_regs = ()  # pre-define

    def __init__(self, *a, **kw):
        self.arch = dict(
            regs = self.__regs__,
            endian = self.__endian__,
            bitsize = self.__bitsize__,
        )
        self.pc_reg = self.__pc__
        super(QRSP, self).__init__(*a, **kw)
