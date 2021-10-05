__all__ = [
    "ThreadStreamCopier"
]

from collections import (
    namedtuple,
)
from threading import (
    current_thread,
    Lock,
)


class ThreadStreamCopier(object):
    """ A stream wrapper that can copy data originated from different
threads to different streams. Wrapped stream is also given the data.
    """

    def __init__(self, stream):
        self.stream = stream
        self.thread_streams = {} # Thread -> stream
        self._lock = Lock()

    def write(self, *a):
        with self._lock:
            self.stream.write(*a)
            try:
                thread_stream = self.thread_streams[current_thread()]
            except KeyError:
                pass
            else:
                thread_stream.write(*a)

    def flush(self, *a):
        with self._lock:
            self.stream.flush(*a)
            try:
                thread_stream = self.thread_streams[current_thread()]
            except KeyError:
                pass
            else:
                thread_stream.flush(*a)

    def __setitem__(self, thread, stream):
        self.thread_streams[thread] = stream

    def __getitem__(self, thread):
        return self.thread_streams[thread]

    def __delitem__(self, thread):
        del self.thread_streams[thread]

    def __contains__(self, thread):
        return thread in self.thread_streams

    def __call__(self, stream):
        "Use as `with copier(stream):`"
        return _CopyContext(self, current_thread(), stream)

    @classmethod
    def catch_stdout(cls):
        import sys
        copier = ThreadStreamCopier(sys.stdout)
        sys.stdout = copier
        return copier

    def release_stdout(self):
        import sys
        sys.stdout = self.stream


class _CopyContext(namedtuple("_CopyContext_", "copier thread stream")):

    def __enter__(self):
        copier, thread, stream = self
        assert thread not in copier
        copier[thread] = stream
        return self

    def __exit__(self, *__):
        copier, thread, stream = self
        assert copier[thread] is stream
        del copier[thread]
