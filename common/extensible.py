__all__ = [
    "Extensible"
]

from .pygen import (
    const_types
)


class Extensible(object):
    "Remembers attributes added to it and support serialization to Python."

    def __init__(self, **kw):
        kw["_Extensible__added"] = set(kw)
        self.__dict__.update(kw)

    def __setattr__(self, n, v):
        if n.startswith("_Extensible__"):
            raise AttributeError("Setting auxiliary attribute %s" % n)
        object.__setattr__(self, n, v)

    def __delattr__(self, n):
        if n.startswith("_Extensible__"):
            raise AttributeError("Deleting auxiliary attribute %s" % n)
        return object.__delattr__(self, n)

    @property
    def _py_serializable(self):
        for o in iter(getattr(self, a) for a in self.__added):
            if hasattr(o, "__gen_code__") or isinstance(o, const_types):
                yield o

    def __dfs_children__(self):
        return tuple(self._py_serializable)

    def __gen_code__(self, g):
        g.reset_gen()
        for a in self.__added:
            g.gen_field(a, getattr(self, a))
        g.gen_end()

    def __repr__(self):
        res = type(self).__name__ + "(\n"
        kw = []
        for a in self.__added:
            kw.append("    " + a + " = " + repr(getattr(self, a)))
        res = res + ",\n".join(kw) + "\n)"
        return res
