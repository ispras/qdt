__all__ = [
    "LineNoStream"
]


from bisect import (
    bisect_right,
)
from .soft_stream import (
    SoftStream,
)


def iter_lines(start, limit, eol = b"\r\n"):
    fmt = b"%d" + eol
    for l in range(start, limit):
        yield fmt % l


def lines_data(start, limit, **settings):
    """
>>> # this bytes comparison way supports doctest under both Py2 & Py3
>>> lines_data(8, 11) == b'8\\r\\n9\\r\\n10\\r\\n'
True
    """
    return b"".join(iter_lines(start, limit, **settings))


def bytes_of_decade(d, eol_size = 2):
    # 0\r\n ... 9\r\n : 10 * (1 + 2); digits in decade == 1, eol_size == 2
    # 10\r\n ... 99\r\n : (100 - 10) * (2 + 2)
    # 100\r\n ... 999\r\n : (1000 - 100) * (3 + 2)
    # ...

    if d == 1:
        prev_decade = 0
    else:
        prev_decade = 10 ** (d - 1)
    return (10 ** d - prev_decade) * (d + eol_size)


all_decade_offsets = []

def offset2decade(offset, eol_size = 2):
    """
>>> offset2decade(0)
1
>>> offset2decade(1)
1
>>> offset2decade(29)
1
>>> offset2decade(30)
2
>>> offset2decade(len(lines_data(0, 100)))
3
>>> offset2decade(len(lines_data(0, 1000)))
4
>>> offset2decade(len(lines_data(0, 10000)) - 1)
4
    """
    try:
        decade_offsets = all_decade_offsets[eol_size]
    except IndexError:
        for __ in range(len(all_decade_offsets), eol_size + 1):
            decade_offsets = [0]
            all_decade_offsets.append(decade_offsets)

    idx = bisect_right(decade_offsets, offset)

    if idx == len(decade_offsets):
        last_offset = decade_offsets[-1]
        while True:
            last_offset += bytes_of_decade(idx)
            decade_offsets.append(last_offset)
            if offset < last_offset:
                return idx
            idx += 1
    else:
        return idx


def offset2line_offset(offset, eol_size = 2):
    """
>>> offset2line_offset(lines_data(0, 100).find(b"21"))
(21, 0)
>>> offset2line_offset(lines_data(0, 1000).find(b"321"))
(321, 0)
>>> offset2line_offset(lines_data(0, 10000).find(b"4321"))
(4321, 0)
>>> offset2line_offset(lines_data(0, 10000).find(b"\\r\\n321\\r\\n"))
(320, 3)
    """
    decade = offset2decade(offset, eol_size = eol_size)

    # Note, required cache all_decade_offsets[eol_size] is already defined by
    # `offset2decade` above.
    decade_intra_offset = offset - all_decade_offsets[eol_size][decade - 1]

    line_size = decade + eol_size
    lineno, line_offset = divmod(decade_intra_offset, line_size)
    if decade > 1:
        lineno += 10 ** (decade - 1)
    return lineno, line_offset


class LineNoStream(SoftStream):
    """
>>> s = LineNoStream(19, eol = b"\\n")
>>> # this bytes comparison way supports doctest under both Py2 & Py3
>>> s.read() == b'0\\n1\\n2\\n3\\n4\\n5\\n6\\n7\\n8\\n9'
True
>>> s.read(1) == b''
True
>>> s = LineNoStream(100)
>>> s.seek(30) # skip first decade
30
>>> s.read(4) == b'10\\r\\n'
True
>>> s.read(2) == b'11'
True
>>> s.seek(2, 1)
38
>>> s.read(2) == b'12'
True
    """

    def __init__(self, size, eol = b"\r\n"):
        super(LineNoStream, self).__init__(size)

        self._eol = eol
        self._eol_size = len(eol)
        self._fmt = b"%d" + eol

    def _read_iter(self, size):
        fmt = self._fmt

        offset = self._offset
        self._offset = size + offset
        lineno, line_offset = offset2line_offset(offset, self._eol_size)
        line_data = fmt % lineno

        if line_offset > 0:
            chunk = line_data[line_offset:line_offset + size]
            yield chunk
            size -= len(chunk)
            lineno += 1
            line_data = fmt % lineno

        while size > 0:
            chunk = line_data[:size]
            yield chunk
            size -= len(chunk)
            lineno += 1
            line_data = fmt % lineno
