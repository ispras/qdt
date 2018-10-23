__all__ = [
    "lazy"
]

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
