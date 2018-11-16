__all__ = [
    "LineAdapter"
      , "IdentityAdapter"
]

from abc import (
    ABCMeta,
    abstractmethod
)


class LineAdapter(object):
    """ An abstract base class is an interface that defines the methods that
any 'line adapter' must implement.
"""
    __metaclass__ = ABCMeta

    @abstractmethod
    def adapt_lineno(self, fname, lineno, opaque):
        pass

    @abstractmethod
    def failback(self):
        pass


class IdentityAdapter(LineAdapter):

    def adapt_lineno(self, fname, lineno, _):
        return fname, int(lineno)

    def failback(self):
        raise RuntimeError("Can't find a line")
