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

    # there must be at least one target for adaptation
    num_targets = 1

    # any line adapter must adapt the lines
    @abstractmethod
    def adapt_lineno(self, fname, lineno, suffix):
        pass

    def failback(self):
        raise RuntimeError("Can't find a line")


class IdentityAdapter(LineAdapter):

    def adapt_lineno(self, fname, lineno, _):
        return fname, int(lineno)
