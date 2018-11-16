__all__ = [
    "LineAdapter"
      , "IdentityAdapter"
]

from abc import (
    ABCMeta,
    abstractmethod
)


class LineAdapter(object):
    """ This abstract base class defines common interface for 'line adapter'.

adapt_lineno: method must return 'tuple(file name, adapted line number)'.
failback: method must raise some exception.

For example see 'IdentityAdapter' realization.
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
