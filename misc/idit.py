""" Image eDITor
"""

from common import (
    callco,
    CLICoDispatcher,
    CoReturn,
    intervalmap,
    lazy,
    mlget as _,
)
from widgets import (
    add_scrollbars_native,
    AutoPanedWindow,
    GUITk,
    TextCanvas,
    VarTreeview,
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


class Padding(Subregion):

    fill_val = b"\x00" # can has arbitrary length

    # Fill value is checked by chunk per time (an optimisation).
    max_chunk_size = 1024 # >= fill_val

    def __init__(self, *a, **kw):
        self._test_fill_val = kw.pop("test_fill_val", False)
        super(Padding, self).__init__(*a, **kw)

    def co_interpret(self):
        if not self._test_fill_val:
            return

        fval = self.fill_val
        flen = len(fval)

        vals = self.max_chunk_size // flen

        if not vals:
            raise NotImplementedError("fill value is too long")

        test_chunk = fval * vals
        chunk_size = vals * flen
        size = len(self)
        limit = size - chunk_size + 1

        offset = 0
        while offset < limit:
            yield True
            next_offset = offset + chunk_size
            if test_chunk != self[offset:next_offset]:
                raise RegionFormatError
            offset = next_offset

        if offset < size:
            yield True
            if self[offset:size] != test_chunk[:size - offset]:
                raise RegionFormatError


class ValueRegion(Subregion):

    def __init__(self, region, *a, **kw):
        kw.setdefault("size", 4)
        super(ValueRegion, self).__init__(region, *a, **kw)

    def co_interpret(self):
        self._bytes = self[0:len(self)]
        return
        yield

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


class Bitfield(object):

    offset = 0
    bitsize = 1

    def __init__(self, int_region):
        self.int_region = int_region

    @lazy
    def len_mask(self):
        return (1 << self.bitsize) - 1

    @lazy
    def mask(self):
        return self.len_mask << self.offset

    @lazy
    def value(self):
        int_val = self.int_region.value
        return (int_val & self.mask) >> self.offset

    def __str__(self):
        return str(self.value)

    def __bool__(self):
        return bool(self.value)


class BitfieldRegion(IntegerRegion):

    bitfields = dict()

    def __init__(self, region, *a, **kw):
        kw.setdefault("signed", False)
        self._test_reserved = kw.pop("test_reserved", True)
        super(BitfieldRegion, self).__init__(region, *a, **kw)

    def co_interpret(self):
        yield super(BitfieldRegion, self).co_interpret()

        if self._test_reserved:
            full_mask = 0
            for name, Cls in self.bitfields.items():
                bf = Cls(self)
                full_mask |= bf.mask
                setattr(self, name, bf)

            if self.value & ~full_mask:
                raise RegionFormatError("reserved")
        else:
            for name, Cls in self.bitfields.items():
                setattr(self, name, Cls(self))


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


class QCOW3Feats(BitfieldRegion):

    def __init__(self, *a, **kw):
        kw.setdefault("size", 8)
        super(QCOW3Feats, self).__init__(*a, **kw)


class QCOW3DirtyBit(Bitfield):
    """If this bit is set then refcounts may be inconsistent, make sure to
scan L1/L2 tables to repair refcounts before accessing the image.
    """
    offset = 0

class QCOW3CorruptBit(Bitfield):
    """If this bit is set then any data structure may be corrupt and the
image must not be written to (unless for regaining consistency).
    """
    offset = 1

class QCOW3ExtDataFileBit(Bitfield):
    """If this bit is set, an external data file is used. Guest clusters are
then stored in the external data file. For such images, clusters in the
external data file are not refcounted. The offset field in the Standard
Cluster Descriptor must match the guest offset and neither compressed clusters
nor internal snapshots are supported.

An External Data File Name header extension may be present if this bit is set.
    """
    offset = 2

class QCOW3CompressionTypeBit(Bitfield):
    """If this bit is set, a non-default compression is used for compressed
clusters. The compression_type field must be present and not zero.
    """
    offset = 3

class QCOW3ExtL2Bit(Bitfield):
    """If this bit is set then L2 table entries use an extended format that
allows subcluster-based allocation.
    """
    offset = 4


class QCOW3IncompatFears(QCOW3Feats):
    """Bitmask of incompatible features. An implementation must fail to open
an image if an unknown bit is set.
    """

    bitfields = dict(
        dirty = QCOW3DirtyBit,
        corrupt = QCOW3CorruptBit,
        ext_data_file = QCOW3ExtDataFileBit,
        compression_type = QCOW3CompressionTypeBit,
        ext_l2 = QCOW3ExtL2Bit,
    )


class QCOW3LazyRefCountBit(Bitfield):
    """If this bit is set then lazy refcount updates can be used. This means
marking the image file dirty and postponing refcount metadata updates.
    """
    offset = 0


class QCOW3CompatFears(QCOW3Feats):
    """Bitmask of compatible features. An implementation can safely ignore any
unknown bits that are set.
    """

    bitfields = dict(
        lazy_ref_count = QCOW3LazyRefCountBit,
    )


class QCOW3BitmapExtBit(Bitfield):
    """This bit indicates consistency for the bitmaps extension data.

It is an error if this bit is set without the bitmaps extension present.

If the bitmaps extension is present but this bit is unset, the bitmaps
extension data must be considered inconsistent.
    """
    offset = 0

class QCOW3RawExtDataBit(Bitfield):
    """If this bit is set, the external data file can be read as a consistent
standalone raw image without looking at the qcow2 metadata.

Setting this bit has a performance impact for some operations on the image
(e.g. writing zeros requires writing to the data file instead of only setting
the zero flag in the L2 table entry) and conflicts with backing files.

This bit may only be set if the External Data File bit (incompatible feature
bit 1) is also set.
    """
    offset = 1

class QCOW3AutoclearFeats(QCOW3Feats):
    """Bitmask of auto-clear features. An implementation may only write to an
image with unknown auto-clear features if it clears the respective bits from
this field first.
    """

    bitfields = dict(
        bitmap_ext = QCOW3BitmapExtBit,
        raw_ext_data = QCOW3RawExtDataBit,
    )


class QCOW3Header(Subregion):

    def __init__(self, region, **kw):
        super(QCOW3Header, self).__init__(region, size = 104, **kw)

    def co_interpret(self):
        self.magic = magic = ValueRegion(self, 0)
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
            incompatible_features = (QCOW3IncompatFears, (72,)),
            compatible_features = (QCOW3CompatFears, (80,)),
            autoclear_features = (QCOW3AutoclearFeats, (88,)),
            refcount_order = (QCOW3Integer, (96,)),
            header_length = (QCOW3Integer, (100,)),
        )


class QCOW3HeaderExtension(Subregion):

    def co_interpret(self):
        self.type = type_ = QCOW3Integer(self)
        yield type_.co_interpret()

        self.length = length = QCOW3Integer(self, 4)
        yield length.co_interpret()

        ext_data_len = length.value
        self.ext_data = Subregion(self, 8, ext_data_len)

        pad_len = (8 - (ext_data_len & 0x7)) & 0x7

        if pad_len:
            pad = Padding(self, 8 + ext_data_len, pad_len,
                test_fill_val = True,
            )
            yield pad.co_inerpret()
        else:
            pad = None

        self.pad = pad

        self._size = 8 + ext_data_len + pad_len


class QCOW3L2RefcntBlockOffset(QCOW3Offset):

    def co_interpret(self):
        yield super(QCOW3L2RefcntBlockOffset, self).co_interpret()

        if self.value & 0xFF:
            raise RegionFormatError("reserved")


class QCOW3Image(Subregion):

    def co_interpret(self):
        self.header = header = QCOW3Header(self)
        yield header.co_interpret()

        if header.crypt_method != 0:
            raise RegionFormatNotImplemented

        if header.incompatible_features != 0:
            raise RegionFormatNotImplemented

        if header.compatible_features != 0:
            raise RegionFormatNotImplemented

        if header.autoclear_features != 0:
            raise RegionFormatNotImplemented

        offset = 104

        self.extensions = exts = {}

        while True:
            ext = QCOW3HeaderExtension(self, offset)
            yield ext.co_interpret()
            etype = ext.type
            if etype == 0:
                break
            exts[etype.value] = ext
            offset += len(ext)

        self.l1_refcnt_table = Subregion(self,
            header.refcount_table_offset.value,
            size = header.refcount_table_clusters.value * self.cluster_size
        )

        self.refcnt_blocks = dict()

        self.l1_cluster_table= Subregion(self,
            header.l1_table_offset.value,
            size = header.l1_size.value << 3
        )

    @lazy
    def backing_file(self):
        h = self.header
        offset = h.backing_file_offset.value
        if offset == 0:
            return None

        backing_file_bytes = self[offset:offset + h.backing_file_size.value]
        backing_file = backing_file_bytes.decode("utf-8")
        return backing_file

    @lazy
    def cluster_size(self):
        return 1 << self.header.cluster_bits.value

    @lazy
    def refcount_bits(self):
        return 1 << self.header.refcount_order.value

    @lazy
    def refount_mask(self):
        return (1 << self.refcount_bits) - 1

    @lazy
    def refcount_block_entries(self):
        return (self.cluster_size << 3) // self.refcount_bits

    def co_get_refcount(self, offset):
        cluster = offset // self.cluster_size
        refcount_table_index = cluster // self.refcount_block_entries

        l1rt = self.l1_refcnt_table
        block_offset = QCOW3L2RefcntBlockOffset(l1rt,
            refcount_table_index << 3
        )
        yield block_offset.co_interpret()

        block_offset_value = block_offset.value

        if block_offset_value == 0:
            # Not allocated
            raise CoReturn(0)

        refcnt_blocks = self.refcnt_blocks
        if refcount_table_index in refcnt_blocks:
            block = refcnt_blocks[refcount_table_index]
        else:
            block = Subregion(self, block_offset_value,
                size = self.cluster_size
            )
            refcnt_blocks[refcount_table_index] = block

        refcount_block_index = cluster % self.refcount_block_entries
        refcount_bits = self.refcount_bits
        refcount_bitoffset = refcount_block_index * refcount_bits
        refcount_lo_bit = refcount_bitoffset + refcount_bits
        refcount_start = refcount_bitoffset >> 3
        refcount_end = (refcount_lo_bit + 7) >> 3

        refcount_bytes = block[refcount_start:refcount_end]
        refcount = int.from_bytes(refcount_bytes, "big", signed = False)

        shift = (8 - refcount_bitoffset) & 0x3
        refcount = (refcount >> shift) & self.refount_mask

        raise CoReturn(refcount)


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
    root = Idit()
    root.file_name = image
    root.mainloop()


class Idit(GUITk, object):

    def __init__(self, *a, **kw):
        GUITk.__init__(self, *a, **kw)

        self._file_name = None
        self._stream = None
        self._region = None

    @property
    def file_name(self):
        return self._file_name

    @file_name.setter
    def file_name(self, file_name):
        if self._file_name == file_name:
            return
        self.stream = open(file_name, "rb")
        self._file_name = file_name

    @property
    def stream(self):
        return self._stream

    @stream.setter
    def stream(self, stream):
        if self._stream is stream:
            return
        if self._stream is not None:
            self._stream.close()

        self._file_name = None

        region = QCOW3Image(RegionCache(StreamRegion(stream)))
        self.task_manager.enqueue(self._co_change_region(region))

    @property
    def region(self):
        return self._region

    def _co_change_region(self, region):
        # TODO: wait current region to complete
        self._region = region
        yield region.co_interpret()

        print(region.backing_file)

        print((yield region.co_get_refcount(0)))
        print((yield region.co_get_refcount(1 << 20)))
        print((yield region.co_get_refcount(1 << 30)))


if __name__ == "__main__":
    exit(main() or 0)
