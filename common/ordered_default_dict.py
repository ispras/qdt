__all__ = [
    "OrderedDefaultDict"
]


from collections import (
    OrderedDict,
)


class OrderedDefaultDict(OrderedDict):

    def __init__(self, factory):
        self.factory = factory

    def __missing__(self, key):
        self[key] = v = self.factory()
        return v
