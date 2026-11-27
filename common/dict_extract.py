__all__ = [
    "dict_extract"
      , "kw_extract"
]

from .reflection import (
    default_args,
)

from itertools import (
    chain,
)

def dict_extract(src, *keys, **defaults):
    pop = src.pop
    contains = src.__contains__
    ret = dict((n, pop(n, d)) for (n, d) in defaults.items())
    ret.update((n, pop(n)) for n in keys if contains(n))
    return ret


containers = set, list, tuple, dict

def _i2names(i):
    if isinstance(i, str):
        return (i,)
    if isinstance(i, containers):
        return i
    if isinstance(i, type):
        # TODO: __new__?
        i = i.__init__
    # `i` is expected to be `__call__`able
    return default_args(i)

ichain = chain.from_iterable

def kw_extract(kw, *items):
    return dict_extract(kw, *ichain(map(_i2names, items)))
