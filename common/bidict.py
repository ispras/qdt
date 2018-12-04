__all__ = [
    "bidict"
]

from .lazy import (
    lazy
)

_dsi = dict.__setitem__

# Some discussion about overriding `dict` methods is here:
# https://stackoverflow.com/questions/2060972/subclassing-python-dictionary-to-override-setitem


class bidict(dict):
    "Bidirectional dict."

    # new methods

    def key(self, v, default_key = None):
        "Opposite to `get`."
        return self.mirror.get(v, default_key)

    @lazy
    def mirror(self):
        """ Symmetric `bidict`. It internally binded with this one so changes
to one of them are propagated to another.
        """
        m = bidict()
        m.__dict__["mirror"] = self
        return m

    # implementation

    def __init__(self, *a, **kw):
        dict.__init__(self, *a, **kw)
        if self:
            m = self.mirror
            for k, v in self.items():
                _dsi(m, v, k)

    def __setitem__(self, k, v):
        _dsi(self, k, v)
        _dsi(self.mirror, v, k)

    def __delitem__(self, k):
        v = dict.__getitem__(self, k)
        dict.__delitem__(self, k)
        dict.__delitem__(self.mirror, v)

    def update(self, *a, **kw):
        dict.update(self, *a, **kw)

        m = self.mirror
        if a:
            other = a[0]
            for k in other:
                _dsi(m, other[k], k)

        for k, v in kw.items():
            _dsi(m, v, k)

    def setdefault(self, k, value = None):
        if k not in self:
            self.__setitem__(k, value)
        return dict.__getitem__(self, k)

    def pop(self, *a):
        l = len(a)
        if l == 1:
            k = a[0]
            # if `k` not in `self`, a `KeyError` is raised
            v = self.__getitem__(k)
            self.__delitem__(k)
        elif l == 2:
            k, v = a
            if k in self:
                v = self.__getitem__(k)
                self.__delitem__(k)
        else:
            raise TypeError(
                "pop expected either 1 or 2 arguments, got: %u" % len(a)
            )

        return v
