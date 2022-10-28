__all__ = (
    "TypeContainer",
)

from common import (
    lazy,
)
from inspect import (
    getmro,
)


class TypeContainer(object):
    """ A superclass for everything that can contain `Type`s or
`TypeContainer`s in its attributes.

It accounts `__type_references__` attribute in entire inheritance chain.

Extra references may be used to apply extended (semantic) order when syntax
order does not meet all requirements.
    """

    def __init__(self,
        origin = None,
    ):
        self.extra_references = set()
        self.origin = origin

    __type_references__ = ("extra_references",)

    @lazy
    def __type_attributes__(self):
        return type_referencing_attributes(type(self))


def type_referencing_attributes(cls, cache = {}):
    try:
        ret = cache[cls]
    except KeyError:
        ret = cache[cls] = tuple(iter_type_referencing_attributes(cls))
    return ret


# TODO: there are too many `EMPTY` constants in the project already...
EMPTY = tuple()

def iter_type_referencing_attributes(cls):
    for superclass in getmro(cls):
        for t in superclass.__dict__.get("__type_references__", EMPTY):
            yield t
