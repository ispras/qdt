"""
Notes.

* `reset_cache` vs `reset_lazy`
    `reset_cache` may be faster if there are many NON-evaluated `@cached`
    attributes.
    `reset_lazy` does not require extra attribute (`__lazy__`).

* `lazy` is analogue to `functools.cached_property`.
    But, it's available on any Python.

"""

__all__ = [
    "lazy"
      , "cached"
  , "reset_cache"
  , "iter_lazy"
  , "iter_lazy_items"
]

from inspect import (
    getmro,
)

# See: https://docs.python.org/2/howto/descriptor.html
# In Russian: https://habr.com/post/122082/

class lazy(object):

    def __init__(self, getter):
        self.getter = getter
        doc = getter.__doc__ or ""

        self.__doc__ = doc + "\nlazy: evaluated on demand."

    def __get__(self, obj, cls):
        getter = self.getter
        val = getter(obj)
        # Add evaluated value to `__dict__` of `obj` to prevent consequent call
        # to `__get__` of this non-data descriptor. Note that direct access to
        # the `__dict__` instead of `getattr` prevents possible conflict with
        # custom `__getattr__` / `__getattribute__` implementation.
        obj.__dict__[getter.__name__] = val
        return val


class cached(lazy):
    """ Variant of `lazy` attribute decorator that saves names of evaluated
lazy attributes to list with name `__lazy__`. An instance with `cached`
attributes must provide such an attribute (by `__init__`, for example).
    """

    def __get__(self, obj, cls):
        getter = self.getter
        val = getter(obj)
        name = getter.__name__
        obj.__dict__[name] = val
        obj.__lazy__.append(name)
        return val

def reset_cache(obj):
    "Resets lazily evaluated `cached` attributes of `obj`."

    l = obj.__lazy__
    pop = obj.__dict__.pop
    for name in l:
        pop(name, None)
    del l[:]


def iter_lazy(o):
    overridden = set()
    override = overridden.add

    for t in getmro(type(o)):
        for n, v in t.__dict__.items():

            if n in overridden:
                continue
            override(n)

            if isinstance(v, lazy):
                yield n


def iter_lazy_items(o):
    for n in iter_lazy(o):
        yield (n, getattr(o, n))


def reset_lazy(o):
    "Resets lazily evaluated `lazy` attributes of `obj`."
    pop = o.__dict__.pop
    for n in iter_lazy(o):
        pop(n, None)
