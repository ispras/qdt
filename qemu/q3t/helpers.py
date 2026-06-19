__all__ = [
    # look bottom
]

from functools import (
    lru_cache,
)
from itertools import (
    starmap,
)
from struct import (
    pack,
    unpack,
)


def q3t_u2f(u):
    return unpack("f", pack("I", u))[0]

def q3t_f2u(f):
    return unpack("I", pack("f", f))[0]

def q3t_u2d(u):
    return unpack("d", pack("Q", u))[0]

def q3t_d2u(d):
    return unpack("Q", pack("d", d))[0]

def q3t_join_be(*uu, **kw):
    shift = kw.pop("shift", 32)
    res = 0
    for u in uu:
        res <<= shift
        res |= u
    return res

def q3t_jbe8(*a, **kw):
    kw["shift"] = 8
    return q3t_join_be(*a, **kw)

def q3t_jbe16(*a, **kw):
    kw["shift"] = 16
    return q3t_join_be(*a, **kw)

def q3t_jbe32(*a, **kw):
    kw["shift"] = 32
    return q3t_join_be(*a, **kw)

def q3t_jle8(*a, **kw):
    kw["shift"] = 8
    return q3t_join_le(*a, **kw)

def q3t_jle16(*a, **kw):
    kw["shift"] = 16
    return q3t_join_le(*a, **kw)

def q3t_jle32(*a, **kw):
    kw["shift"] = 32
    return q3t_join_le(*a, **kw)

def q3t_join_le(*uu, **kw):
    return q3t_join_be(*reversed(uu), **kw)

def q3t_iter_le(u, shift = 32):
    mask = (1 << shift) - 1
    while u:
        yield u & mask
        u >>= shift

def q3t_le(*a, **kw):
    return tuple(q3t_iter_le(*a, **kw))

def q3t_iter_be(*a, **kw):
    return reversed(tuple(q3t_iter_le(*a, **kw)))

def q3t_be(*a, **kw):
    return tuple(q3t_iter_be(*a, **kw))

def q3t_be8(*a, **kw):
    kw["shift"] = 8
    return q3t_be(*a, **kw)

def q3t_be16(*a, **kw):
    kw["shift"] = 16
    return q3t_be(*a, **kw)

def q3t_be32(*a, **kw):
    kw["shift"] = 32
    return q3t_be(*a, **kw)

def q3t_le8(*a, **kw):
    kw["shift"] = 8
    return q3t_le(*a, **kw)

def q3t_le16(*a, **kw):
    kw["shift"] = 16
    return q3t_le(*a, **kw)

def q3t_le32(*a, **kw):
    kw["shift"] = 32
    return q3t_le(*a, **kw)

def q3t_bits(*shifts):
    res = 0
    for shift in shifts:
        res |= 1 << shift
    return res

def q3t_negN(i, bitsize):
    mask = (1 << bitsize) - 1
    return ((i ^ mask) + 1) & mask

def q3t_neg8(i):
    return q3t_negN(i, 8)

def q3t_neg16(i):
    return q3t_negN(i, 16)

def q3t_neg32(i):
    return q3t_negN(i, 32)

def q3t_neg40(i):
    return q3t_negN(i, 40)

def q3t_neg64(i):
    return q3t_negN(i, 64)

def q3t_neg80(i):
    return q3t_negN(i, 80)

def q3t_neg128(i):
    return q3t_negN(i, 128)

def q3t_o(bitsize, i):
    "integer overflow emulation in python"
    return i & ((1 << bitsize) - 1)

def q3t_o8(i):
    return q3t_o(8, i)

def q3t_o16(i):
    return q3t_o(16, i)

def q3t_o32(i):
    return q3t_o(32, i)

def q3t_o40(i):
    return q3t_o(40, i)

def q3t_o64(i):
    return q3t_o(64, i)

def q3t_o80(i):
    return q3t_o(80, i)

def q3t_o128(i):
    return q3t_o(128, i)

def q3t_vo8(v):
    return type(v)(map(q3t_o8, v))

def q3t_vo16(v):
    return type(v)(map(q3t_o16, v))

def q3t_vo32(v):
    return type(v)(map(q3t_o32, v))

def q3t_vo40(v):
    return type(v)(map(q3t_o40, v))

def q3t_vo64(v):
    return type(v)(map(q3t_o64, v))

def q3t_vo128(v):
    return type(v)(map(q3t_o128, v))

@lru_cache
def q3t_opf(op):
    return eval("lambda a, b : a %s b" % op)

def q3t_op(op, a, b):
    return q3t_opf(op)(a, b)

def q3t_vop(op, va, vb):
    return type(va)(starmap(q3t_opf(op), zip(va, vb)))

def q3t_vadd(*vv):
    return q3t_vop("+", *vv)

def q3t_vsub(*vv):
    return q3t_vop("-", *vv)

def q3t_vmul(*vv):
    return q3t_vop("*", *vv)

def q3t_vfdiv(*vv):
    return q3t_vop("/", *vv)

def q3t_vidiv(*vv):
    return q3t_vop("//", *vv)

def q3t_vand(*vv):
    return q3t_vop("&", *vv)

def q3t_vor(*vv):
    return q3t_vop("|", *vv)

def q3t_vxor(*vv):
    return q3t_vop("^", *vv)


__all__.extend(
    n for n in globals() if n.startswith("q3t_")
)
