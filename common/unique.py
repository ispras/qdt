__all__ = [
    "iter_unique",
    "list_of_unique"
  , "iter_unique_tuples"
  , "iter_file_unique_subpaths"
]


from .ordered_default_dict import (
    OrderedDefaultDict,
)

from os import (
    sep,
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


EMPTY = tuple()

def iter_unique_tuples(pairs, **kw):
    d = OrderedDefaultDict(list)
    for k, v in pairs:
        # `v` can be an iterator already
        i = iter(v)
        head = next(i)
        tail = i
        d[head].append((k, tail))
    if len(d) == 1:
        # `head` is common for all, skip it
        skipped = kw.get("skipped", EMPTY)
        for __, tails in d.items():
            if len(tails) == 1:
                yield tails[0][0], skipped
                continue
            for k, v in iter_unique_tuples(tails, **kw):
                yield k, skipped + v
    else:
        for head, tails in d.items():
            if len(tails) == 1:
                yield tails[0][0], (head,)
                continue
            for k, v in iter_unique_tuples(tails, **kw):
                yield k, (head,) + v


def iter_file_unique_subpaths(file_names,
    pre = reversed,
    post = sep.join,
    skipped = ("",)
):
    for f, t in iter_unique_tuples(
        ((f, pre(f.split(sep))) for f in file_names),
        skipped = skipped,
    ):
        yield f, post(t)
