__all__ = [
    "DictStack"
]


from .empty_dict import (
    EmptyDict,
)


class DictStack(dict):

    def __init__(self, backing = EmptyDict()):
        super(DictStack, self).__init__()
        self.backing = backing

    def __missing__(self, key):
        return self.backing[key]

    def push(self):
        return DictStack(backing = self)
