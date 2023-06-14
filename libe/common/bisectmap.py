__all__ = [
    "BisectMap"
]

from bisect import (
    bisect_left,
)
from six.moves import (
    zip as izip,
)


def _no_factory(key):
    raise KeyError(key)


class BisectMap(object):

    __slots__ = ("_keys", "_values", "_factory")

    def __init__(self, factory = _no_factory):
        self._keys = []
        self._values = []
        self._factory = factory

    def __iter__(self):
        return iter(self._keys)

    def __reversed__(self):
        return reversed(self._keys)

    def keys(self):
        return iter(self._keys)

    def values(self):
        return iter(self._values)

    def items(self):
        return izip(self._keys, self._values)

    def max(self):
        return self._keys[-1]

    def min(self):
        return self._keys[0]

    def __setitem__(self, k, v):
        _keys = self._keys
        i = bisect_left(_keys, k)
        if i == len(_keys):
            _keys.append(k)
            self._values.append(v)
        if _keys[i] == k:
            self._values[i] = v
        else:
            _keys.insert(i, k)
            self._values.insert(i, v)

    def setdefault(self, k, v):
        _keys = self._keys
        i = bisect_left(_keys, k)
        if i == len(_keys):
            _keys.append(k)
            self._values.append(v)
        if _keys[i] != k:
            _keys.insert(i, k)
            self._values.insert(i, v)

    def __getitem__(self, k):
        _keys = self._keys
        i = bisect_left(_keys, k)
        if i == len(_keys) or _keys[i] != k:
            v = self._factory(k)
            _keys.insert(i, k)
            self._values.insert(i, v)
            return v
        else:
            return self._values[i]

    def __delitem__(self, k):
        _keys = self._keys
        i = bisect_left(_keys, k)
        if i == len(_keys) or _keys[i] != k:
            raise KeyError(k)
        _keys.pop(i)
        self._values.pop(i)

    def get(self, k, default = None):
        _keys = self._keys
        i = bisect_left(_keys, k)
        if i == len(_keys) or _keys[i] != k:
            return default
        return self._values[i]

    def pop(self, k, *default):
        _keys = self._keys
        i = bisect_left(_keys, k)
        if i == len(_keys) or _keys[i] != k:
            if default:
                return default[0]
            else:
                raise KeyError(k)
        _keys.pop(i)
        return self._values.pop(i)
