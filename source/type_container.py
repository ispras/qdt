__all__ = (
    "TypeContainer",
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

    def __init__(self):
        self.extra_references = set()

    __type_references__ = ("extra_references",)

    def iter_type_attributes(self):
        for superclass in getmro(type(self)):
            if hasattr(superclass, "__type_references__"):
                for t in superclass.__type_references__:
                    yield t

    @property
    def __type_attributes__(self):
        return tuple(self.iter_type_attributes())
