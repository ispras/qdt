__all__ = [
    "listen_stream"
  , "listen_out"
  , "listen_err"
  , "listen_all"
  , "orig_stderr_write"
]

from collections import (
    namedtuple,
)
from functools import (
    wraps,
)
import sys
from threading import (
    Lock,
)
from traceback import (
    print_exc,
)


orig_stderr_write = sys.stderr.write


class StreamListener(namedtuple(
    "_StreamListener", "stream orig_write listener wrapper"
)):

    def revert(self):
        if self.stream.write is self.wrapper:
            self.stream.write = self.orig_write


class StreamListeners(tuple):

    def revert(self):
        for sl in self:
            sl.revert()


def listen_stream(stream, listener, locked = False):

    write = stream.write

    if locked:
        lock = Lock()

        @wraps(write)
        def write_wrapper(*a, **kw):
            try:
                with lock:
                    listener(*a, **kw)
            except:
                stream_listener.revert()
                orig_stderr_write("Failed stream listener " +
                    " %s is replaced with original function %s" % (
                        listener, write
                    )
                )
                print_exc()

            return write(*a, **kw)
    else:
        @wraps(write)
        def write_wrapper(*a, **kw):
            listener(*a, **kw)
            return write(*a, **kw)

    stream.write = write_wrapper

    stream_listener = StreamListener(stream, write, listener, write_wrapper)
    return stream_listener


def listen_out(listener, **kw):
    return listen_stream(sys.stdout, listener, **kw)


def listen_err(listener, **kw):
    return listen_stream(sys.stderr, listener, **kw)


def listen_all(listener, **kw):
    return StreamListeners((
        listen_out(listener, **kw),
        listen_err(listener, **kw)
    ))
