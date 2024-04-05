__all__ = [
    "re_newline"
  , "Index"
      , "LineIndex"
      , "FixedLinesizeIndex"
  , "LineIndexIsNotReady"
]

from six.moves.cPickle import (
    dump,
    load,
)
from re import (
    compile,
)


class Index(object):

    def __init__(self,
        blob_size = 64 << 10, # 64 KiB
    ):
        self.blob_size = blob_size
        self.index = None
        self.total_lines = None

        # self.current_lines # only available while `co_build` is in process

    def load(self, file_name):
        state = load(file_name)

        (
            self.total_lines,
            self.index,
        ) = state

    def save(self, file_name):
        total_lines = self.total_lines
        if total_lines is None:
            raise LineIndexIsNotReady

        state = (
            total_lines,
            self.index,
        )

        dump(state, file_name)

    def build(self, stream):
        for __ in self.co_build(stream):
            pass

    def co_build(self, stream):
        raise NotImplementedError

    def lookup(self, lineidx):
        raise NotImplementedError

    def read_chunk(self, stream, lineidx):
        """ Reads the `stream` and returns `tuple`:
[0]: b'ytes' of the chunk containing `lineidx`-th line start
[1]: number of the line starting at the chunk 0-th offset
        """
        return next(self.iter_chunks(stream, lineidx = lineidx))

    def iter_chunks(self, stream, lineidx = 0):
        lineidx, offset = self.lookup(lineidx)

        read = stream.read
        seek = stream.seek
        size = self.blob_size

        while True:
            # support shared access to the stream between `yield`s
            seek(offset)
            data = read(size)
            if data == b"":
                break
            offset += len(data)
            yield (data, lineidx)
            # consequent blobs are not line-aligned, generally
            lineidx = None


re_newline = compile(b"\n|(\r\n)|\r")


class LineIndex(Index):
    """ Index of lines offsets in a text file.

Lines enumeration starts from 0.
    """

    def __init__(self,
        # index[i] = offset of ((i + 1) * 1024)-th line
        lines_chunk_bits = 10,
        **kw
    ):
        super(LineIndex, self).__init__(**kw)
        self.lines_chunk_bits = lines_chunk_bits
        self.lines_chunk = lines_chunk = 1 << lines_chunk_bits
        self.lines_chunk_mask = lines_chunk - 1

    def iter_line_offsets(self, stream, offset = 0):
        # local cache
        blob_size = self.blob_size
        fiter = re_newline.finditer
        read = stream.read
        seek = stream.seek

        prev_line_offset = 0

        while True:
            # support shared access to the stream between `yield`s
            seek(offset)
            chunk = read(blob_size)
            if not chunk:
                yield prev_line_offset
                break # EOF

            for mi in fiter(chunk):
                yield prev_line_offset
                prev_line_offset = offset + mi.end()

            offset += len(chunk)

            # b"\r\n" can be split in two chunks.
            # Note, `chunk[-1]` works differently under Py2 than Py3.
            if chunk[-1:] == b'\r':
                seek(offset)
                c = read(1)
                if len(c) == 0:
                    yield prev_line_offset
                    break # EOF

                offset += 1

                if c == b'\r':
                    # An empty line after the chunk.
                    # b'\r' is used as a line separator in the file.
                    yield prev_line_offset
                    prev_line_offset += 1
                elif c == b'\n':
                    # That line starts a bit later.
                    prev_line_offset += 1

    def co_build(self, stream):
        # local cache
        blob_size = self.blob_size
        lines_chunk_mask = self.lines_chunk_mask
        index = self.index = []
        append = index.append

        lineidx = 0

        oter = self.iter_line_offsets(stream, offset = 0)
        # skip 0-th line
        next(oter)

        prev_pause_offset = 0

        while True:
            self.current_lines = lineidx
            yield True # always can continue

            for lineidx, offset in enumerate(oter, lineidx + 1):
                if lineidx & lines_chunk_mask == 0:
                    append(offset)

                if offset - prev_pause_offset >= blob_size:
                    prev_pause_offset = offset
                    break
            else:
                # EOF
                break

        del self.current_lines
        self.total_lines = lineidx + 1

    def lookup(self, lineidx):
        bits = self.lines_chunk_bits
        i = lineidx >> bits
        if i == 0:
            lineidx = 0
            offset = 0
        else:
            lineidx = i << bits
            offset = self.index[i - 1]
        return (lineidx, offset)


class LineIndexIsNotReady(RuntimeError):
    pass


class FixedLinesizeIndex(Index):

    def __init__(self, linesize = 1, **kw):
        super(FixedLinesizeIndex, self).__init__(**kw)
        self.linesize = linesize

    def lookup(self, lineidx):
        return (lineidx, self.linesize * lineidx)

    def co_build(self, stream):
        linesize = self.linesize
        self.current_lines = self.total_lines = \
            (stream.seek(0, 2) + linesize - 1) // linesize
        return
        yield # must be a coroutine
