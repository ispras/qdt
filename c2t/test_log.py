__all__ = [
    "TestLog"
  , "iter_dump_lines"
]

from collections import (
    defaultdict,
    deque,
)
from os import (
    linesep as os_linesep,
)
from time import (
    gmtime,
    strftime,
    time,
)


def default_timestamp_formatter(ts):
    return strftime("%H:%M:%S", gmtime(ts)) + ".%03f" % (ts % 1.0)


class TestLog(object):

    def __init__(self):
        self._runner2log = defaultdict(deque)

    def log(self, runner, dump, timestamp = None):
        if timestamp is None:
            timestamp = time()
        self._runner2log[runner].append((timestamp, dump))

    def iter_lines(self, runner,
        with_time = True,
        timestamp_base = 0.0,
        timestamp_formatter = default_timestamp_formatter,
    ):
        log = self._runner2log[runner]

        for ts, dump in log:
            if with_time:
                rts = ts - timestamp_base
                yield "time"
                yield "  " + timestamp_formatter(rts)

            if isinstance(dump, str):
                # special dumps are `str`ings
                lter = iter(str(dump).splitlines(False))
            else:
                # regular dumps are `dict`s
                lter = iter_dump_lines(dump)

            for l in lter:
                yield l

    def log_lines(self, runner, **iter_lines_kw):
        return list(self.iter_lines(runner, **iter_lines_kw))

    def joined_lines(self, runner, linesep = os_linesep, **iter_lines_kw):
        return linesep.join(self.log_lines(runner, **iter_lines_kw)) + linesep

    def to_file(self, runner, file_name, **kw):
        text = self.joined_lines(runner, **kw)
        with open(file_name, "w") as f:
            f.write(text)

    def iter_runners(self):
        return iter(self._runner2log)


def iter_dump_lines(dump):
    """ Formatting of lines is adapter for usage with text file comparison
tools (ex.: diff, meld).
    """

    # Source level terms are first as they are expected to have less
    # difference.
    yield "lineno"
    yield "  " + str(dump["lineno"])
    if "vars" in dump:
        yield "vars:"
        for name, value in sorted(dump["vars"].items()):
            # Variable name can has any type (str, bytes, ...).
            if not isinstance(name, str):
                try:
                    name = name.decode("utf-8")
                except:
                    name = str(name)

            yield "  " + name
            # Variable value is an integer.
            yield "    {v} (0x{v:x})".format(v = value)

    # Hardware level terms are second as they are expected to have differences,
    # even if the test is correct.
    yield "addr"
    # Address is a hexadecimal string.
    yield "  " + dump["addr"].decode("charmap")
    yield "regs"
    for name, value in sorted(dump["regs"].items()):
        yield "  " + name
        # Reg value is a hexadecimal string.
        yield "    " + value.decode("charmap")
