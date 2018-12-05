#!/usr/bin/python

# Refs:
# https://docs.sympy.org/latest/python-comparisons.html

from traceback import (
    format_exc
)


def prex(expr):
    print(expr + " # evaluation...")
    try:
        res = eval(expr)
    except:
        print("! failure:\n%s\n" % format_exc())
    else:
        print("# result: %s" % res)


class A(object):

    def __init__(self, a, hash):
        self.a = a
        self._hash = hash

    def __lt__(self, o):
        print "%s.__lt__(%s)" % (self.a, o.a)
        return NotImplemented

    def __le__(self, o):
        print "%s.__le__(%s)" % (self.a, o.a)
        return NotImplemented

    def __gt__(self, o):
        print "%s.__gt__(%s)" % (self.a, o.a)
        return NotImplemented

    def __ge__(self, o):
        print "%s.__ge__(%s)" % (self.a, o.a)
        return NotImplemented

    def __cmp__(self, o):
        print "%s.__cmp__(%s)" % (self.a, o.a)
        # return cmp(self._hash, o._hash)
        return NotImplemented

    def __eq__(self, o):
        print "%s.__eq__(%s)" % (self.a, o.a)
        return NotImplemented

    def __ne__(self, o):
        print "%s.__ne__(%s)" % (self.a, o.a)
        return NotImplemented

    def __hash__(self):
        print "%s.__hash__()" % (self.a)
        return self._hash


show = prex

a = A("a", 1)
b = A("b", 2)
c = A("c", 3)
d = A("d", 1)

show("a == b")
show("a != b")
show("a < b")
show("a <= b")
show("a > b")
show("a >= b")
show("sorted([a, b, c])")
show("{d: 5}")
show("a in {d: 5}")
show("set([d, d, d])")
show("a in set([d, d, d])")
show("set([a, b])")


print("--- x = set([a, b]); y = set([a, b]); ---")
x = set([a, b])
y = set([a, b])
prex("x == y")

print("--- x = set([a, b]); y = set([b, d]); ---")
x = set([a, b])
y = set([b, d])
prex("x == y")


class Simple(object): pass


o1 = Simple()
o2 = Simple()
prex("o1 == o2")

d1 = dict(a = 1, b = 2)
d2 = dict(b = 2, a = 1)
prex("d1 == d2")


class DictMatch(Simple):

    def __eq__(self, obj):
        return self.__dict__ == obj.__dict__


dm1, dm2 = DictMatch(), DictMatch()

prex("dm1 == dm2")


class WithList(DictMatch):

    def __init__(self, *a):
        self.a = a


wl1, wl2 = WithList(1, 2, 3), WithList(3, 2, 1)

prex("wl1 == wl2")


class WithSet(DictMatch):

    def __init__(self, *a):
        self.a = set(a)


ws1, ws2 = WithSet(1, 2, 3), WithSet(3, 2, 1)

prex("ws1 == ws2")

from collections import (
    Counter
)


class CounterMatch(WithList):

    def __eq__(self, obj):
        return Counter(self.a) == Counter(obj.a)


cm1, cm2 = CounterMatch(1, 2, 3), CounterMatch(3, 2, 1)

prex("cm1 == cm2")

cm1_l, cm2_l = CounterMatch([1], [2], [3]), CounterMatch([3], [2], [1])

prex("cm1_l == cm2_l")


class HashMatch(WithList):

    def __eq__(self, obj):
        return sum(hash(x) for x in self.a) == sum(hash(x) for x in obj.a)


hm1, hm2 = HashMatch(1, 2, 3), HashMatch(3, 2, 1)

prex("hm1 == hm2")

hm1_l, hm2_l = HashMatch([1], [2], [3]), HashMatch([3], [2], [1])

prex("hm1_l == hm2_l")

hm1_wl = HashMatch(WithList(1), WithList(2))
hm2_wl = HashMatch(WithList(2), WithList(1))

prex("hm1_wl == hm2_wl")

class HashedList(WithList):

    def __hash__(self):
        return sum(hash(i) for i in self.a)


hm1_hl = HashMatch(HashedList(1), HashedList(2))
hm2_hl = HashMatch(HashedList(2), HashedList(1))

prex("hm1_hl == hm2_hl")

hl1_hl = HashedList(HashedList(1), HashedList(2))
hl2_hl = HashedList(HashedList(2), HashedList(1))

prex("hl1_hl == hl2_hl")


class HashedListNoEq(HashedList):

    __eq__ = object.__eq__


hlne1_hl = HashedListNoEq(HashedList(1), HashedList(2))
hlne2_hl = HashedListNoEq(HashedList(2), HashedList(1))

prex("hlne1_hl == hlne2_hl")


class HashedListHashDict(HashedList):

    def __eq__(self, obj):
        return hash(self.__dict__) == hash(obj.__dict__)


hlhd1_hl = HashedListHashDict(HashedList(1), HashedList(2))
hlhd2_hl = HashedListHashDict(HashedList(2), HashedList(1))

prex("hlhd1_hl == hlhd2_hl")


class HashedListCounterDict(HashedList):

    def __eq__(self, obj):
        return Counter(self.__dict__) == Counter(obj.__dict__)


hlcd1_hl = HashedListCounterDict(HashedList(1), HashedList(2))
hlcd2_hl = HashedListCounterDict(HashedList(2), HashedList(1))

prex("hlcd1_hl == hlcd2_hl")

hlcd1_hlne = HashedListCounterDict(HashedListNoEq(1), HashedListNoEq(2))
hlcd2_hlne = HashedListCounterDict(HashedListNoEq(2), HashedListNoEq(1))

prex("hlcd1_hlne == hlcd2_hlne")
