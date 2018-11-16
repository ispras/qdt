__all__ = [
    "LineAdapter"
      , "IdentityAdapter"
]

from abc import (
    ABCMeta,
    abstractmethod
)


class LineAdapter(object):
    """ This class defines common interface for 'line adapter'.
For example see 'IdentityAdapter' default 'line adapter' class realization.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def adapt_lineno(self, fname, lineno, opaque):
        """
    :param fname:
        is file in which `lineno` should be adapted
    :lineno line number that should be adapted
    :opaque auxiliary information for `line` adaptation
    :returns:
        `fname` and adapted `lineno`

        """
        pass

    @abstractmethod
    def failback(self):
        """
    :returns:
        file name and line number if it can, else it raises some exception

        """
        pass


class IdentityAdapter(LineAdapter):

    def adapt_lineno(self, fname, lineno, _):
        return fname, int(lineno)

    def failback(self):
        raise RuntimeError("Can't find a line")
