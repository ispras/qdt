__all__ = [
    "iter_unique",
    "list_of_unique"
]


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
