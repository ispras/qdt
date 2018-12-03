__all__ = [
    "hash_container"
]

from .intervalmap import (
    intervalmap
)
from .ordered_set import (
    OrderedSet
)


def hash_set(v):
    "Ignores order"
    return hash(sum(hash_container(e) for e in v))

def hash_mapping(m):
    "Ignores order"
    return hash(sum(hash((n, hash_container(v))) for n, v in m.items()))


# Exact type match. Inherited classes must provide __hash__.
HASH_ALG = {
    dict : hash_mapping,
    intervalmap : hash_mapping,
    tuple : hash_set,
    list : hash_set,
    set : hash_set,
    OrderedSet : hash_set
}


def hash_container(c):
    return HASH_ALG.get(type(c), hash)(c)


hash_container.__doc__ = """
Recursively hashes containers. For rest types uses `hash`. Supported container
types: %s
""" % (
    ", ".join(cls.__name__ for cls in HASH_ALG.keys())
)
