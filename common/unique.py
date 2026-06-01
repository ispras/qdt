__all__ = [
    "iter_unique",
    "list_of_unique"
  , "iter_unique_tuples"
]


from .ordered_default_dict import (
    OrderedDefaultDict,
)


def iter_unique(i):
    "Iterates i skipping repeated items and preserving order of items."
    yielded = set()
    add = yielded.add
    for ii in i:
        if ii in yielded:
            continue
        yield ii
        add(ii)


def list_of_unique(i):
    return list(iter_unique(i))


def iter_unique_tuples(pairs):
    d = OrderedDefaultDict(list)
    for k, v in pairs:
        # `v` can be an iterator already
        i = iter(v)
        head = next(i)
        tail = i
        d[head].append((k, tail))
    if len(d) == 1:
        # `head` is common for all, skip it
        for __, tails in d.items():
            if len(tails) == 1:
                yield tails[0][0], tuple()
                continue
            for k, v in iter_unique_tuples(tails):
                yield k, v
    else:
        for head, tails in d.items():
            if len(tails) == 1:
                yield tails[0][0], (head,)
                continue
            for k, v in iter_unique_tuples(tails):
                yield k, (head,) + v
