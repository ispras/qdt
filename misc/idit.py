""" Image eDITor
"""

from common import (
    CLICoDispatcher,
    intervalmap,
    lazy,
)

from argparse import (
    ArgumentParser,
)


class Region(object):

    def __getitem__(self, offset_or_slice):
        raise NotImplementedError

    def __setitem__(self, offset_or_slice):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError

    def co_interpret_subregions(self, **fields):
        for name, (Cls, args) in fields.items():
            field = Cls(self, *args)
            setattr(self, name, field)
            yield field.co_interpret()


class StreamRegion(Region):

    def __init__(self, stream):
        self._stream = stream
        self._size = size = stream.seek(0, 2)
        self._last = size - 1
        self._seek = stream.seek
        self._read = stream.read
        self._write = stream.write

    def __len__(self):
        return self._size

    def __getitem__(self, oos):
        if isinstance(oos, slice):
            start = oos.start
            stop = oos.stop
            step = oos.step

            if start is None:
                start = 0
            elif start < 0:
                raise ValueError

            if stop is None:
                stop = self._size
            elif self._size < stop:
                raise ValueError

            if stop <= start:
                raise NotImplementedError

            if step is None:
                step = 1

            if step == 1:
                self._seek(start)
                return self._read(stop - start)
            else:
                raise NotImplementedError
        else:
            if oos < 0 or self._last < oos:
                raise ValueError

            self._seek(oos)
            return self._read(1)

    def __setitem__(self, oos, value):
        if isinstance(oos, slice):
            start = oos.start
            stop = oos.stop
            step = oos.step

            if start is None:
                start = 0
            elif start < 0:
                raise ValueError

            if stop is None:
                stop = self._size
            elif self._size < stop:
                raise ValueError

            if stop <= start:
                raise NotImplementedError

            size = start - stop
            if size != len(value):
                raise ValueError

            if step is None:
                step = 1

            if step == 1:
                self._seek(start)
                return self._write(value)
            else:
                raise NotImplementedError
        else:
            if oos < 0 or self._last < oos:
                raise ValueError

            if len(value) != 1:
                raise ValueError

            self._seek(oos)
            return self._write(value)


def join_sum(first, *chunks):
    for c in chunks:
        first += c
    return first


class RegionCache(Region):

    def __init__(self, region):
        self._backing = region
        self._size = len(region)
        self._cache = intervalmap()

    def __len__(self):
        return self._size

    def _iter_chunks(self, start, stop):
        cache = self._cache
        i = cache.iter_items_from(start)
        back = self._backing

        cur = start
        for (bs, be), v in i:
            if cur < bs:
                left_v = back[cur:bs]
                # Size of internal intervalmap structures should not change.
                # It's safe to continue iteration.
                v = left_v + v
                cache[cur:be] = v
            elif cur == bs:
                if stop < be:
                    v = v[:stop - bs]
            else: # bs < cur
                if stop < be:
                    v = v[cur - bs : stop - bs]
                else:
                    v = v[cur - bs:]

            yield v

            if stop <= be:
                break

            cur = be

        if cur < stop:
            right_v = back[cur:stop]
            try:
                if cur == be:
                    # join with last chunk
                    cache[bs:stop] = v + right_v
                else:
                    cache[cur:stop] = right_v
            except NameError: # be
                # no iterations performed by the loop above
                cache[cur:stop] = right_v

            yield right_v

    def __getitem__(self, oos):
        if isinstance(oos, slice):
            start = oos.start
            stop = oos.stop
            step = oos.step

            if start is None:
                start = 0
            elif start < 0:
                raise ValueError

            if stop is None:
                stop = self._size
            elif self._size < stop:
                raise ValueError

            if stop <= start:
                raise NotImplementedError

            if step is None:
                step = 1

            if step == 1:
                return join_sum(*self._iter_chunks(start, stop))
            else:
                raise NotImplementedError
        else:
            if oos < 0 or self._last < oos:
                raise ValueError

            return next(self._iter_chunks(start, start + 1))

    def __setitem__(self, oos, value):
        raise NotImplementedError


class Subregion(Region):

    def __init__(self, region, offset = 0, size = None):
        self._region = region
        self._offset = offset
        if size is None:
            size = len(region) - offset
        self._size = size

    def __len__(self):
        return self._size

    def __getitem__(self, oos):
        offset = self._offset
        if isinstance(oos, slice):
            start = oos.start
            stop = oos.stop
            step = oos.step

            if start is None:
                start = 0
            elif start < 0:
                raise ValueError

            if stop is None:
                stop = self._size
            elif self._size < stop:
                raise ValueError

            start += offset
            stop += offset

            return self._region[start:stop:step]
        else:
            if oos < 0 or self._size <= oos:
                raise ValueError
            return self._region[oos + offset]

    def __setitem__(self, oos, value):
        offset = self._offset
        if isinstance(oos, slice):
            start = oos.start
            stop = oos.stop
            step = oos.step

            if start is None:
                start = 0
            elif start < 0:
                raise ValueError

            if stop is None:
                stop = self._size
            elif self._size < stop:
                raise ValueError

            start += offset
            stop += offset

            self._region[start:stop:step] = value
        else:
            if oos < 0 or self._size <= oos:
                raise ValueError
            self._region[oos + offset] = value


class ValueRegion(Subregion):

    def co_interpret(self):
        self._bytes = self[0:len(self)]

    @lazy
    def bytes(self):
        return self._bytes

    def __eq__(self, other):
        if isinstance(other, bytes):
            return self._bytes == other
        elif type(self) is not type(other):
            return False
        else:
            return self._bytes == other._bytes

    @lazy
    def value(self):
        return self.__decode__()

    def __decode__(self):
        raise NotImplementedError

    def __str__(self):
        try:
            return str(self.value)
        except:
            return repr(self._bytes)


BE = "big"
LE = "little"


class IntegerRegion(ValueRegion):

    def __init__(self, region, *a, **kw):
        self._byteorder = kw.pop("byteorder", LE)
        self._signed = kw.pop("signed", True)
        super(IntegerRegion, self).__init__(region, *a, **kw)


    def __decode__(self):
        return int.from_bytes(self._bytes, self._byteorder,
            signed = self._signed
        )

    def __eq__(self, other):
        if isinstance(other, int):
            return self.value == other
        else:
            return super(IntegerRegion, self).__eq__(other)


class RegionException(Exception):
    pass


class RegionFormatUnknown(RegionException):
    "The region is likely in different format."


class RegionFormatNotImplemented(RegionException):
    "The region format is right but current implementation cannot decode it."


class RegionFormatError(RegionException):
    "The region format is right but encoding has errors."


class QCOW3Integer(IntegerRegion):

    def __init__(self, *a, **kw):
        kw["byteorder"] = BE
        kw.setdefault("signed", False)
        kw.setdefault("size", 4)
        super(QCOW3Integer, self).__init__(*a, **kw)


class QCOW3Offset(QCOW3Integer):

    def __init__(self, *a, **kw):
        kw.setdefault("size", 8)
        super(QCOW3Offset, self).__init__(*a, **kw)


class QCOW3Header(Subregion):

    def __init__(self, region, **kw):
        super(QCOW3Header, self).__init__(region, size = 72, **kw)

    def co_interpret(self):
        self.magic = magic = ValueRegion(self, 0, 4)
        yield magic.co_interpret()

        if magic != b"QFI\xfb":
            raise RegionFormatUnknown

        self.version = version = QCOW3Integer(self, 4)
        yield version.co_interpret()

        if version != 3:
            raise RegionFormatNotImplemented

        yield self.co_interpret_subregions(
            backing_file_offset = (QCOW3Offset, (8,)),
            backing_file_size = (QCOW3Integer, (16,)),
            cluster_bits = (QCOW3Integer, (20,)),
            size = (QCOW3Offset, (24,)),
            crypt_method = (QCOW3Integer, (32,)),
            l1_size = (QCOW3Integer, (36,)),
            l1_table_offset = (QCOW3Offset, (40,)),
            refcount_table_offset = (QCOW3Offset, (48,)),
            refcount_table_clusters = (QCOW3Integer, (56,)),
            nb_snapshots = (QCOW3Integer, (60,)),
            snapshots_offset = (QCOW3Offset, (64,)),
        )

        if self.crypt_method != 0:
            raise RegionFormatNotImplemented


class QCOW3Image(Subregion):

    def co_interpret(self):
        self.header = header = QCOW3Header(self)
        yield header.co_interpret()


def main():
    ap = ArgumentParser(
        description = "Image eDITor",
    )
    arg = ap.add_argument
    arg("image")
    args = ap.parse_args()
    return idit(**vars(args))


def idit(
    image,
):
    disp = CLICoDispatcher()
    image_stream = open(image, "rb")

    qcow2img = QCOW3Image(RegionCache(StreamRegion(image_stream)))

    disp.enqueue(qcow2img.co_interpret())
    disp.dispatch_all()

    print(qcow2img)


if __name__ == "__main__":
    exit(main() or 0)
