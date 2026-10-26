""" Random Number Generators
"""

__all__ = [
    "murmur_step"
  , "MurMur"
]

def murmur_step(x, h):
    x += h
    x *= 0x7fd652ad
    x &= 0xFFFFFFFF
    x ^= x >> 16

    x *= 0x7fd652ad
    x &= 0xFFFFFFFF
    x ^= x >> 10

    x *= 0x7fd652ad
    x &= 0xFFFFFFFF
    x ^= x >> 17
    return x


class MurMur:

    def __init__(self, h = 0xDEADBEEF, x = None):
        if x is None:
            x = h
        self.h = h
        self.x = x

    def __iter__(self):
        return self

    def __next__(self):
        self.x = x = murmur_step(self.x, self.h)
        return x
