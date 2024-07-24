__all__ = [
    "EmptyDict"
  , "WritingEmptyDict"
]


class WritingEmptyDict(AssertionError):
    pass


class EmptyDict(object):

    def __getitem__(self, key):
        raise KeyError(key)

    def __setitem__(self, *kv):
        raise WritingEmptyDict(*kv)

    def __delitem__(self, key):
        raise KeyError(key)

    def __contains__(self, __):
        return False

    def __iter__(self):
        return
        yield  # must be an iterator

    def __reversed__(self):
        return
        yield  # must be an iterator
