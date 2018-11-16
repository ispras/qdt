__all__ = [
    "LineAdapter"
]

from abc import (
    ABCMeta,
    abstractmethod
)


class LineAdapter:
    """ An abstract base class is an interface that defines the methods that
any 'line adapter' must implement.
"""
    __metaclass__ = ABCMeta

    # there must be at least one target for adaptation
    num_targets = 1

    # any line adapter must adapt the lines
    @abstractmethod
    def adapt_lineno(self, fname, lineno, _):
        pass
