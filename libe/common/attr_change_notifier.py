__all__ = [
    "AttributeChangeNotifier",
]


from .events import (
    notify,
)

class AttributeChangeNotifier:
    """
>>> from libe.common.events import (
...     listen,
... )

>>> class AttrChTest(AttributeChangeNotifier):
...     pass
>>> o = AttrChTest()

>>> def setattr_listener(n, v):
...     print("o.%s <= %r (prev. %r)" % (n, v, getattr(o, n, None)))
>>> listen(o, "setattr", setattr_listener)
>>> o.a = 1
o.a <= 1 (prev. None)

>>> def delattr_listener(n,):
...     print("del o.%s (prev. %r)" % (n, getattr(o, n)))
>>> listen(o, "delattr", delattr_listener)
>>> del o.a
del o.a (prev. 1)
    """

    __slots__ = tuple()  # don't enforce `__dict__`

    def __setattr__(self, *a):
        # allow to get previous value by `notify`-ing before
        try:
            notify(self, "setattr", *a)
        finally:
            object.__setattr__(self, *a)

    def __delattr__(self, *a):
        # allow ... (see `__setattr__`)
        try:
            notify(self, "delattr", *a)
        finally:
            object.__delattr__(self, *a)
