__all__ = [
    "re_newline",
    "LineIndex",
    "LineIndexIsNotReady"
]


from six.moves.cPickle import (
    dump,
    load,
)
from re import (
    compile,
)


re_newline = compile(b"\n|(\r\n)\r")


class LineIndex(object):
    """ Index of lines offsets in a text file.

Lines enumeration starts from 0.
    """

    def __init__(self,
        # index[i] = offset of ((i + 1) * 1024)-th line
        lines_chunk_bits = 10,
        blob_size = 64 << 10, # 64 KiB
    ):
        self.lines_chunk_bits = lines_chunk_bits
        self.lines_chunk = lines_chunk = 1 << lines_chunk_bits
        self.lines_chunk_mask = lines_chunk - 1
        self.blob_size = blob_size

        # self.current_lines # only available while `co_build` is in process
        self.index = None
        self.total_lines = None

    def load(self, file_name):
        state = load(file_name)

        (
            self.total_lines,
            self.index,
        ) = state

    def build(self, stream):
        for __ in self.co_build(stream):
            pass

    def co_build(self, stream):
        # local cache
        blob_size = self.blob_size
        lines_chunk_mask = self.lines_chunk_mask
        fiter = re_newline.finditer
        index = self.index = []
        append = index.append

        lineidx = 0
        offset = 0

        stream.seek(0)
        read = stream.read

        while True:
            self.current_lines = lineidx
            yield True # always can continue

            chunk = read(blob_size)
            if not chunk:
                break # EOF

            for lineidx, mi in enumerate(fiter(chunk), lineidx + 1):
                if lineidx & lines_chunk_mask == 0:
                    append(offset + mi.end())

            # Note: `offset += len(chunk)` is only better at EOF but have
            # no effect.
            offset += blob_size

            # b"\r\n" is split in two chunks.
            if chunk[-1] == b'\r':
                self.current_lines = lineidx
                yield True # pause before blocking I/O

                c = read(1)
                if len(c) == 0:
                    break # EOF

                offset += 1

                if c == b'\r':
                    # An empty line after the chunk.
                    # b'\r' is used as a line separator in the file.
                    lineidx += 1
                    if lineidx & lines_chunk_mask == 0:
                        append(offset)
                elif c == b'\n':
                    if lineidx & lines_chunk_mask == 0:
                        # `lineidx`-th line start a bit later.
                        index[-1] += 1

        del self.current_lines
        self.total_lines = lineidx + 1

    def save(self, file_name):
        total_lines = self.total_lines
        if total_lines is None:
            raise LineIndexIsNotReady

        state = (
            total_lines,
            self.index,
        )

        dump(state, file_name)

    def read_chunk(self, stream, lineidx):
        """ Reads the `stream` and returns `tuple`:
[0]: b'ytes' of the chunk containing `lineidx`-th line start
[1]: number of the line starting at the chunk 0-th offset
        """
        return next(self.iter_chunks(stream, lineidx = lineidx))

    def iter_chunks(self, stream, lineidx = 0):
        bits = self.lines_chunk_bits
        lines_chunk = self.lines_chunk

        i = lineidx >> bits
        if i == 0:
            stream.seek(0)
            lineidx = 0
        else:
            lineidx = i << bits
            offset = self.index[i - 1]
            stream.seek(offset)

        read = stream.read
        size = self.blob_size

        while True:
            data = read(size)
            if data == b"":
                break
            yield (data, lineidx)
            lineidx += lines_chunk


class LineIndexIsNotReady(RuntimeError):
    pass
