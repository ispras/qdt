__all__ = [
    "HexStream"
]

from .soft_stream import (
    SoftStream,
)

from six import (
    PY2,
)

hex_fmt = b"%02X".__mod__

if PY2:
    def swap_bytes(b):
        return "".join(reversed(b))

    def hex_bytes(b):
        return "".join(hex_fmt(ord(i)) for i in b)
else:
    def swap_bytes(b):
        return bytes(reversed(b))

    def hex_bytes(b):
        return b"".join(hex_fmt(i) for i in b)


class HexStream(SoftStream):
    """
>>> from common import OffsetsStream
>>> s = HexStream(
...     OffsetsStream(word_size_bits = 1),
...     group_size = 2, spacing = 2, groups = 3
... )
>>> s.read(2 * 3 * 2 + 1 + 2 * (3 - 1)).decode() # one line: 000204 (swapped)
'3030  3230  3430\\n'
>>> (s.read(4) + s.read(3) + s.read(10)).decode() # next line: 06080a
'3630  3830  6130\\n'
>>> s.le = False
>>> s.read(17).decode() # third line: 0c0e10 (not swapped)
'3063  3065  3130\\n'
>>> s.byte_offset
18
>>> s.read(5).decode() # encoded 12 and space
'3132 '
>>> s.byte_offset
20
>>> s.group_size = 1

After group_size is changed the hex stream appears like this:

30  30  30 | 000
32  30  34 | 204
30  36  30 | 060
38  30  61 | 80a
30  63  30 | 0c0
65  31  30 | e10
31  32 *31 | 121  * byte offset 20
34  31  36 | 416

>>> s.read(5).decode() # encoded 14 and space between
'31\\n34'
>>> s.seek(0)
0
>>> s.read((2 * 3 + 2 * 2 + 1) * 8).decode() # check the table above
'\
30  30  30\\n\
32  30  34\\n\
30  36  30\\n\
38  30  61\\n\
30  63  30\\n\
65  31  30\\n\
31  32  31\\n\
34  31  36\\n\
'

    """

    def __init__(self, stream,
        group_size = 1, # bytes
        spacing = 1, # spaces between groups
        groups = 16, # per line
        le = True, # swap bytes in groul
    ):
        super(HexStream, self).__init__(1)
        self._stream_size = stream.seek(0, 2)
        stream.seek(0)

        self._stream = stream
        self._group_size = group_size
        self._spacing = spacing
        self._groups = groups
        self._le = le

        self._next_grp = 0
        self._chrs = b""
        self._spc = self._spacing
        self._expected_offset = 0

        self._update_size()

    @property
    def bytes_per_line(self):
        return self._groups * self._group_size

    @property
    def offset_per_line(self):
        # Line example: 'GGGG  GGGG  GGGG  GGGG\n'
        #                ^^
        #             one byte
        grps = self._groups
        return (
            ((grps * self._group_size) << 1)
          + (grps - 1) * self._spacing
          + 1 # \n
        )

    @property
    def group_length(self):
        return (self._group_size << 1) + self._spacing

    @property
    def byte_offset(self):
        offset = self._offset
        opl = self.offset_per_line

        line = offset // opl
        offset_in_line =  offset % opl

        grp_len = self.group_length
        grp = offset_in_line // grp_len
        offset_in_group = offset_in_line % grp_len
        byte_in_group = offset_in_group >> 1

        # TODO: le

        return (
            self.bytes_per_line * line
          + grp * self._group_size
          + byte_in_group
        )

    @byte_offset.setter
    def byte_offset(self, byte_offset):
        # _read_iter state and stream state will be synchronized during
        # next _read_iter iteration

        self._offset = self.offset_of_byte(byte_offset)

    def offset_of_byte(self, byte_offset):
        bpl = self.bytes_per_line
        grp_size = self._group_size

        line = byte_offset // bpl
        line_offset = byte_offset % bpl
        grp = line_offset // grp_size
        grp_offset = line_offset % grp_size
        chr_ = (grp_offset << 1)

        # TODO: le

        return (
            self.offset_per_line * line
          + self.group_length * grp
          + chr_
        )

    @property
    def group_size(self):
        return self._group_size

    @group_size.setter
    def group_size(self, group_size):
        # preserve byte_offset
        boff = self.byte_offset
        self._group_size = group_size
        self.byte_offset = boff

        self._update_size()

    @property
    def spacing(self):
        return self._spacing

    @spacing.setter
    def spacing(self, spacing):
        # preserve byte_offset
        boff = self.byte_offset
        self._spacing = spacing
        self.byte_offset = boff

        self._full_spc = b" " * spacing

        self._update_size()

    @property
    def groups(self):
        return self._groups

    @groups.setter
    def groups(self, groups):
        # preserve byte_offset
        boff = self.byte_offset
        self._groups = groups
        self.byte_offset = boff

        self._update_size()

    @property
    def le(self):
        return self._le

    @le.setter
    def le(self, le):
        # preserve byte_offset
        boff = self.byte_offset
        self._le = le
        self.byte_offset = boff

        # _size is not changed

    def _update_size(self):
        ss = self._stream_size
        bpl = self.bytes_per_line
        gs = self._group_size

        lines = ss // bpl
        last_line_len = ss % bpl
        last_grps = last_line_len // gs
        last_grp_len = last_line_len % gs

        self._size = (
            lines * self.offset_per_line
          + last_grps * self.group_length
          + (last_grp_len << 1)
          + 1 # terminating \n
        )

    def _read_iter(self, size):
        gs = self._group_size
        s = self._stream
        read = s.read

        # check offset (e.g. after seek or formatting parameter changing)
        if self._expected_offset != self._offset:
            # recalculate _read_iter state
            offset = self._offset
            opl = self.offset_per_line

            line = offset // opl
            offset_in_line =  offset % opl

            grp_len = self.group_length
            grp = offset_in_line // grp_len
            offset_in_group = offset_in_line % grp_len

            s.seek(self.bytes_per_line * line + grp * self._group_size)
            gbytes = read(gs)

            if gbytes:
                if self._le:
                    gbytes = swap_bytes(gbytes)

                chrs = hex_bytes(gbytes)[offset_in_group:]
                next_grp = grp + 1
                if next_grp == self._groups:
                    chrs += b"\n"
                    self._spc = self._spacing
                    next_grp = 0
                else:
                    self._spc = 0

                self._chrs = chrs
                self._next_grp = next_grp


        last_grp = self._groups - 1
        spcs = self._spacing
        swap = self.le

        next_grp = self._next_grp
        spc = self._spc
        chrs = self._chrs

        rest = size
        while rest:
            if chrs:
                yield chrs[:1]
                rest -= 1
                chrs = chrs[1:]
                continue

            if spc < spcs:
                yield b" "
                rest -= 1
                spc += 1
                continue

            gbytes = read(gs)
            if gbytes:
                if swap:
                    gbytes = swap_bytes(gbytes)

                chrs = hex_bytes(gbytes)

                if next_grp == last_grp:
                    chrs += b"\n"
                    next_grp = 0
                else:
                    spc = 0
                    next_grp = next_grp + 1
            else:
                break # EOF

        self._next_grp = next_grp
        self._spc = spc
        self._chrs = chrs
        offset = self._offset + (size - rest)
        self._expected_offset = offset
        self._offset = offset
