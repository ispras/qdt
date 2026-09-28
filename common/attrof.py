__all__ = [
    "attrof",
]

_BOILERPLATE = """
class attrof_desc(attrof_impl):
    def __get__(self, obj, objtype = None):
        if obj is None:
            return self
        return obj.{path}.{name}

    def __set__(self, obj, value):
        obj.{path}.{name} = value

    def __delete__(self, obj):
        del obj.{path}.{name}
"""

def _gen_descriptor(path, name):
    code = _BOILERPLATE.format(
        path = path,
        name = name,
    )
    ns = {}
    exec(code, globals(), ns)
    return ns["attrof_desc"](path)


class NameIsNotSet(AssertionError): pass

class attrof_impl:

    def __init__(self, path):
        self.path = path

    def __set_name__(self, owner, name):
        # Update the descriptor object in `owner`.
        # This is not enough to set `self.__get__`, `...__set__` and
        #  `...__delete__` attributes.
        setattr(owner, name, _gen_descriptor(self.path, name))

    def _raise(self, o):
        raise NameIsNotSet(type(o).__name__ + "." + self.path)

    def __get__(self, o, t = None):
        self._raise(o)

    def __set__(self, o, v):
        self._raise(o)

    def __delete__(self, o):
        self._raise(o)


def attrof(path, name = None):
    """A helper for `class:` scope defined attributes.
Defines an `instance.attribute` (descriptor) that re-directs access to
another instance.
The another one is pointed by `path` given.
The `path` is a `python.syntax.compatible.expression`.
So, each accees to the `instance.attribute` is redirected to
`instance.python.syntax.compatible.expression.attribute`.
Target attribute `name` can by changed.

E.g.:

class Person:

    def __init__(...
        self.passport = ...

    name = attrof("passport", name = "firstname")
    lastname = attrof("passport")

    """
    if name is None:
        return attrof_impl(path)
    return _gen_descriptor(path, name)
