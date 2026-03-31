__all__ = [
    "StdFilter"
 , "LineFilter"
     , "StdLinePrefixer"
 , "prefix_std"
]

import sys
from time import (
    sleep,
)

class StdFilter(object):

    def __init__(self, stream_name = "stdout", intercept = True):
        self.stream_name = stream_name
        if intercept:
            self.intercept()

    def intercept(self):
        assert not hasattr(self, "stream")
        self.stream = stream = getattr(sys, self.stream_name)
        self.back_write = back_write = stream.write

        def write(data, *a, **kw):
            dataf = self.__filter__(data, *a, **kw)
            attempts = 10
            while attempts:
                try:
                    return back_write(dataf, *a, **kw)
                except BlockingIOError:
                    # This error was only be met during running c2t inside
                    # qemu-kvm virtual machine wth Ubuntu Linux 20.04.
                    sleep(0.1)
                attempts -= 1
            return back_write(dataf, *a, **kw)

        stream.write = write

    def revert(self):
        self.stream.write = self.back_write
        del self.stream
        del self.back_write

    def __filter__(self, data, *a, **kw):
        return data


class LineFilter:

    def __filter__(self, data, *a, **kw):
        return "".join(self._iter_filter(data, a, kw))

    infix = False

    def _iter_filter(self, data, a, kw):
        i = iter(data.splitlines(keepends = True))
        if self.infix:
            for l in i:
                yield self.__infix__(l)
                break
        for l in i:
            yield self.__line__(l)
        if data:
            self.infix = data[-1] not in "\r\n"
        else:
            self.infix = True

    def __infix__(self, data):
        return data

    def __line__(self, prefix):
        return prefix


class StdLinePrefixer(LineFilter, StdFilter):

    def __init__(self, prefix, *a, **kw):
        super(StdLinePrefixer, self).__init__(*a, **kw)
        self.prefix = prefix

    def __line__(self, line):
        return self.prefix + line


def prefix_std(prefix):
    return (
        StdLinePrefixer(prefix),
        StdLinePrefixer(prefix, stream_name = "stderr"),
    )
