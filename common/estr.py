__all__ = [
    "estr"
]

from six import (
    binary_type,
    text_type,
    PY2
)
from codecs import (
    register_error
)
from bisect import (
    bisect_left
)


class estr(tuple):
    """ Encoded STRing.
    """

    def __new__(cls, val, encoding = "utf-8"):
        if isinstance(val, binary_type):
            handler = EStrErrorHandler()
            register_error("estr", handler)
            val = val.decode(encoding, errors = "estr")
            return tuple.__new__(cls, (val, encoding, tuple(handler.errors)))
        elif isinstance(val, text_type):
            # If `val`ue cannot be encoding using custom `encoding`, then it's
            # caller's troubles...
            return tuple.__new__(cls, (val, encoding, tuple())) # No errors
        else:
            raise ValueError("Unsupported value type %s" % type(val))

    if PY2:
        def __str__(self):
            return _item(self, 0).encode("ascii", errors = "replace")
    else:
        def __str__(self):
            return _item(self, 0)

    def __repr__(self):
        return type(self).__name__ + "(%r, %s)" % (
            self.encode(), _item(self, 1)
        )

    def __getitem__(self, index):
        if isinstance(index, slice):
            return self.__getslice(index)
        else:
            return self.__getitem(index)

    def __getitem(self, index):
        errors = _item(self, 2)
        tail_errors = tuple(
            EStrError(offset - index, orig)
                for offset, orig in errors[bisect_left(errors, index):]
        )

        return (
            _item(self, 0).__getitem__(index),
            _item(self, 1),
            tail_errors
        )

    def __getslice(self, slice_):
        start, stop = slice_.start, slice_.stop

        if slice_.step is not None:
            raise NotImplementedError("Only continuous slice")

        errors = _item(self, 2)

        inner_error = tuple(
            EStrError(offset - start, orig)
                for offset, orig in errors[
                    bisect_left(errors, start):bisect_left(errors, stop)]
        )

        return (
            # Py2.__getslice__ or Py3.__getitem__
            _item(self, 0)[slice_],
            _item(self, 1),
            inner_error
        )


    def encode(self, encoding = None):
        val, orig_encoding, errors = self

        ret = b""
        next_correct = 0

        for err_pos, orig in errors:
            ret += val[next_correct:err_pos].encode(orig_encoding) + orig
            next_correct = err_pos + REPLACEMENT_LENGTH

        ret += val[next_correct:].encode(orig_encoding)
        return ret

    # TODO: __add__, __radd__: be careful about offsets in errors

_item = tuple.__getitem__

# The raw string being decoded intentionally has error to get replace character
# Python uses by default.
DEFAULT_REPALCEMENT = b"\xdf".decode("utf-8", "replace")
REPLACEMENT_LENGTH = len(DEFAULT_REPALCEMENT)


class EStrErrorHandler(object):

    def __init__(self):
        self.errors = []

    def __call__(self, exc):
        # exc.args: (encoding, input, start, end, reason)
        input_, start, end =  exc.args[1:4]
        orig = input_[start:end]
        self.errors.append(EStrError((start, orig)))
        return (DEFAULT_REPALCEMENT, end)


class EStrError(tuple):

    # for bisecting error list
    def __lt__(self, offset):
        return self[0] < offset
