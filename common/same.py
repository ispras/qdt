__all__ = [
    "same"
  , "same_attrs"
# Can be used to implement interface of `same`.
# __same__ = same_{implementation}
  , "same_vectors"
  , "same_sets"
  , "same_mappings"
]

from types import (
    GeneratorType
)
from six.moves import (
    zip_longest
)
from collections import (
    Mapping
)


class End(object):
    "Allows `same_vectors` to support iterators."
    __same__ = lambda *_ : False


end = End


def same_vectors(a, b):
    "Recursive. Order sensitive. Complexity is O(min(len(a), len(b)) + 1)."
    for ea, eb in zip_longest(a, b, fillvalue = end):
        if not same(ea, eb):
            return False
    return True


def same_sets(a, b):
    "Recursive. Ignores order. Complexity is O(len(a) * len(b))."
    restb = list(b)
    for ea in a:
        for i, eb in enumerate(restb):
            if same(ea, eb):
                del restb[i]
                break
        else:
            return False
    return not restb


def same_mappings(a, b):
    "Recursive. Ignores order. Complexity is O(min(len(a), len(b)))."
    restb = set(b)
    for ka in a:
        if ka in b:
            ea = a[ka]
            eb = b[ka]
            if same(ea, eb):
                restb.remove(ka)
                continue
        return False
    return not restb


def _same(a, b):
    try:
        __same__ = a.__same__
    except AttributeError:
        return NotImplemented
    return __same__(b)


def _default_same(a, b):
    res =  _same(a, b)
    if res is NotImplemented:
        res = _same(b, a)
    if res is NotImplemented:
        # redirect to base Python comparison mechanism
        return a == b
    return res


def _is_b_iterable(checker):

    def wrapper(a, b):
        # Iterables or not? See: https://stackoverflow.com/a/1952481/7623015
        try:
            _ = (e for e in b)
        except TypeError:
            # This duck does not quack.
            return False
        return checker(a, b)

    wrapper.__doc__ = checker.__doc__

    return wrapper


def _is_b_mapping(checker):

    def wrapper(a, b):
        if isinstance(b, Mapping):
            return checker(a, b)
        return False

    wrapper.__doc__ = checker.__doc__

    return wrapper


# Exact type match. Inherited classes must provide __same__.
SAME_ALG = {
    dict : _is_b_mapping(same_mappings),
    list : _is_b_iterable(same_sets),
    set : _is_b_iterable(same_sets),
    GeneratorType : _is_b_iterable(same_sets),
    tuple : _is_b_iterable(same_vectors)
}


def same(a, b):
    """ Compares a and b using `__same__` method.
At least one of the objects must define it.
If the method is absent, base Python comparison mechanism is involved.

Ex.:
class AClass(ItsParent):

    def __same__(self, other):
        # Look for a semantic difference then return `False`.
        return True # NotImplemented (same result as when no `__same__`)

This allows to implement user defined comparison which is not influences
standard Python operation.
E.g. such operators as `==` and `in` (and using objects as keys in hash
based mappings).
I.e. with this suite it is possible to store semantically same objects
inside one mapping because they will appear different for Python.
It allows an object to be changed after it has been used as a key (if
the object also defines custom `__eq__` or `__hash__`).
For the last reason an `id(obj)` expression result can be used as a key.
But it can be quite inconvenient and disallows to obtain the reference
back by its id.

    """
    alg = SAME_ALG.get(type(a))
    if alg is None:
        alg = SAME_ALG.get(type(b), _default_same)
        a, b = b, a

    return alg(a, b)


same.__doc__ += "\nSupported for those container types:\n\n%s" % ("\n\n".join(
    cls.__name__ + "\n    " + alg.__doc__ for cls, alg in SAME_ALG.items()
))


def same_attrs(a, b, *attrs):
    for name in attrs:
        if not same(getattr(a, name), getattr(b, name)):
            return False
    return True
