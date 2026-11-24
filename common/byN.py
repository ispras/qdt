__all__ = [
    "byN"
  , "by2"
]


from six.moves import (
    zip_longest,
)


def byN(N, iterable, fillvalue = None):
    "Iterates `iterable` by N values at once."
    return zip_longest(*[iter(iterable)] * N, fillvalue = fillvalue)


def by2(i, fill = None):
    i = iter(i)
    for x in i:
        try:
            y = next(i)
        except StopIteration:
            y = fill
        yield x, y
