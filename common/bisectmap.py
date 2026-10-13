__all__ = [
    "BisectMap"
]

from bisect import (
    bisect_left,
)
from itertools import (
    islice,
)
from six.moves import (
    zip,
)


def _no_factory(key):
    raise KeyError(key)


class BisectMap(object):
    """
Keys is only required to be `bisect` compatible.
I.e. implement `__lt__`.
The implementation is only requires this comparison.
    """

    __slots__ = ("_keys", "_values", "_factory")

    def __init__(self, factory = _no_factory):
        self._keys = []
        self._values = []
        self._factory = factory

    def __iter__(self):
        return iter(self._keys)

    def iter_ge_items(self, key):
        keys = self._keys
        i = bisect_left(keys, key)
        return zip(islice(keys, i, None), islice(self._values, i, None))

    def __reversed__(self):
        return reversed(self._keys)

    def keys(self):
        return iter(self._keys)

    def values(self):
        return iter(self._values)

    def items(self):
        return zip(self._keys, self._values)

    def max(self):
        try:
            return self._keys[-1]
        except IndexError:
            return None

    def value_of_max(self):
        try:
            return self._values[-1]
        except IndexError:
            raise KeyError

    def min(self):
        try:
            return self._keys[0]
        except IndexError:
            return None

    def value_of_min(self):
        try:
            return self._values[0]
        except IndexError:
            raise KeyError

    def __bool__(self):
        return bool(self._keys)

    def __setitem__(self, k, v):
        _keys = self._keys
        i = bisect_left(_keys, k)
        if i == len(_keys):
            _keys.append(k)
            self._values.append(v)
        elif k < _keys[i]:
            _keys.insert(i, k)
            self._values.insert(i, v)
        else:
            self._values[i] = v

    def setdefault(self, k, v):
        _keys = self._keys
        i = bisect_left(_keys, k)
        if i == len(_keys):
            _keys.append(k)
            self._values.append(v)
        elif k < _keys[i]:
            _keys.insert(i, k)
            self._values.insert(i, v)

    def get_ge(self, k):
        _keys = self._keys
        i = bisect_left(_keys, k)
        if i == len(_keys):
            raise KeyError(k)
        return self._values[i]

    def __getitem__(self, k):
        _keys = self._keys
        i = bisect_left(_keys, k)
        if i == len(_keys) or k < _keys[i]:
            v = self._factory(k)
            _keys.insert(i, k)
            self._values.insert(i, v)
            return v
        else:
            return self._values[i]

    def __delitem__(self, k):
        _keys = self._keys
        i = bisect_left(_keys, k)
        if i == len(_keys) or k < _keys[i]:
            raise KeyError(k)
        _keys.pop(i)
        self._values.pop(i)

    def get(self, k, default = None):
        _keys = self._keys
        i = bisect_left(_keys, k)
        if i == len(_keys) or k < _keys[i]:
            return default
        return self._values[i]

    def pop(self, k, *default):
        _keys = self._keys
        i = bisect_left(_keys, k)
        if i == len(_keys) or k < _keys[i]:
            if default:
                return default[0]
            else:
                raise KeyError(k)
        _keys.pop(i)
        return self._values.pop(i)
