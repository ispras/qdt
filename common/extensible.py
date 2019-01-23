__all__ = [
    "Extensible"
]

from .pygen import (
    const_types
)

pythonizeable = const_types + (tuple, list, set, dict)


class Extensible(object):
    "Remembers attributes added to it and support serialization to Python."

    def __init__(self, **kw):
        self.__added = set(kw)
        self.__dict__.update(kw)

    def __setattr__(self, n, v):
        if n[0] != '_':
            self.__added.add(n)
        object.__setattr__(self, n, v)

    def __delattr__(self, n):
        if n[0] != '_':
            self.__added.remove(n)
        return object.__delattr__(self, n)

    @property
    def _py_serializable(self):
        for a in self.__added:
            o = getattr(self, a)
            if hasattr(o, "__gen_code__") or isinstance(o, pythonizeable):
                yield a

    @property
    def __pygen_deps__(self):
        return tuple(self._py_serializable)

    def __gen_code__(self, g):
        g.reset_gen(self)
        for a in self.__added:
            g.gen_field(a)
            g.write(" = ")
            g.pprint(getattr(self, a))
        g.gen_end()

    def __repr__(self):
        res = type(self).__name__ + "(\n"
        kw = []
        for a in self.__added:
            kw.append("    " + a + " = " + repr(getattr(self, a)))
        res = res + ",\n".join(kw) + "\n)"
        return res

    def __iter__(self):
        for k in self.__added:
            yield k

    @property
    def _dict(self):
        return dict((k, getattr(self, k)) for k in iter(self))
