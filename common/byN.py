__all__ = [
    "byN"
]


from itertools import (
    zip_longest,
)


def byN(N, iterable, fillvalue = None):
    "Iterates `iterable` by N values at once."
    return zip_longest(*[iter(iterable)] * N, fillvalue = fillvalue)
