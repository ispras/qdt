__all__ = [
    "stdlog"
]

from .lazy import (
    cached,
    reset_cache
)
from six.moves import (
    StringIO
)
import sys # required to replace stdout & stderr at any moment

try:
    from traceback import (
        walk_tb
    )
except ImportError:
    # old Python versions have no that helper
    def walk_tb(tb):
        while tb is not None:
            yield tb.tb_frame, tb.tb_lineno
            tb = tb.tb_next


class stdlog(object):
    "Context manager that captures stdout, stderr and exceptions."

    def __init__(self, hide_exc = False):
        """
@param hide_exc:
    A context manager can hide an exception within `with` block from its outer
    block so the exception may be pooled using `exc` atrribute.
        """
        self._hide_exc = hide_exc

        self.__lazy__ = [] # required by `cached` & `reset_cache` API

    def __enter__(self):
        reset_cache(self)

        self._out, self._err = out, err = StringIO(), StringIO()

        self._back = sys.stdout, sys.stdout
        sys.stdout, sys.stderr = out, err
        return self

    def __exit__(self, *tvt):
        sys.stdout, sys.stdout = self._back
        del self._back

        self.exc = tvt
        return self._hide_exc

    @cached
    def out(self):
        "Captured stdout."
        return self._out.getvalue()

    @cached
    def err(self):
        "Captured stderr."
        return self._err.getvalue()

    @cached
    def e(self):
        "Exception instance."
        return self.exc[1]

    @cached
    def e_traceback(self):
        "Exception traceback."
        return self.exc[2]

    @cached
    def e_type(self):
        "Exception type."
        return self.exc[0]

    @cached
    def r_traceback(self):
        """ Reversed traceback. First returned item is the frame where the
exception happened.
        """
        return list(reversed(list(walk_tb(self.e_traceback))))

    @cached
    def e_file(self):
        "File where the exception has been raised."
        return self.r_traceback[0][0].f_code.co_filename
