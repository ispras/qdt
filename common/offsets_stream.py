__all__ = [
    "OffsetsStream"
]


from .soft_stream import (
    SoftStream,
)


class OffsetsStream(SoftStream):
    """
>>> s = OffsetsStream(word_size_bits = 3)
>>> # this bytes comparison way supports doctest under both Py2 & Py3
>>> s.read(0) == b''
True
>>> s.read(1) == b'0'
True
>>> s.read(7) == b'0000000'
True
>>> s.tell()
8
>>> s.read(8) == b'00000008'
True
>>> s.seek(0xDEADBEEF)
3735928559
>>> # ... b'deadbee0', b'deadbee8', b'deadbef0' ...
>>> #                           ^
>>> s.read(1) == b'8'
True
>>> s.read(3) == b'dea'
True
>>> s.read(8) == b'dbef0dea'
True

>>> s = OffsetsStream(word_size_bits = 2, size = 24)
>>> s.read() == (b"0000" + b"0004" + b"0008" + b"000c" + b"0010" + b"0014")
True
>>> s.read(1) == b''
True
>>> s.read() == b''
True
    """

    def __init__(self,
        word_size_bits = 4, # 16 byte ASCII word contains its 8 byte offset
        size = None,
    ):
        self.word_size_bits = word_size_bits
        self.word_size = word_size = 1 << word_size_bits
        # `word_size` ASCII number represents (`word_size` * 4)-bit integer
        self.offset_mask = (1 << (word_size << 2)) - 1
        self.word_fmt = b"%%0%dx" % word_size

        if size is None:
            size = self.offset_mask + 1
        super(OffsetsStream, self).__init__(size)

    def _read_iter(self, size):
        """ Always poll that generator to the end. Only one active instance
is allowed. Else, `_offset` is inconsistent and output is incorrect.
        """

        offset = self._offset
        offset_mask = self.offset_mask
        fmt = self.word_fmt
        word_size = self.word_size

        bits = self.word_size_bits
        aligned_offset = (offset >> bits) << bits
        word_offset = offset - aligned_offset

        if word_offset:
            word = aligned_offset & offset_mask
            word_bytes = fmt % word
            subword_size = min(size, self.word_size - word_offset)
            yield word_bytes[word_offset:word_offset + subword_size]
            size -= subword_size
            offset += subword_size

        while size >= word_size:
            # Here `offset` is aligned
            yield fmt % (offset & offset_mask)
            offset += word_size
            size -= word_size

        if size > 0:
            word_bytes = fmt % (offset & offset_mask)
            yield word_bytes[:size]
            offset += size

        self._offset = offset
