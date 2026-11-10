__all__ = [
    "BadDedicatedObjectId"
  , "DedicatedObjectIdConflict"
  , "DedicatedObjects"
]

""" Maintains same object graphs in different Python processes
(different memory).
"""

from .bidict import (
    bidict,
)
from .dedicated import (
    Dedicated,
)

from itertools import (
    count,
)

oid2o = bidict()
o2oid = oid2o.mirror

class BadDedicatedObjectId(ValueError): pass
class DedicatedObjectIdConflict(RuntimeError): pass

class DedicatedObjectId: pass
class DedicatedObjectNewId(DedicatedObjectId): pass
class DedicatedAsIs: pass
class DedicatedIterable: pass
class DedicatedDict: pass


def dedicated_object_asis(v):
    if v is None:
        return True
    t = type(v)
    if t in (int, str, float, complex, bool, type):
        return True
    if t is tuple and all(map(dedicated_object_asis, v)):
        return True
    return False


def dedicated_object_getattr(oid, name):
    try:
        o = oid2o[oid]
    except KeyError:
        raise BadDedicatedObjectId(oid)
    return dedicated_object_translate_back(getattr(o, name))


def dedicated_object_translate_back(v):
    if dedicated_object_asis(v):
        return DedicatedAsIs, v
    try:
        return DedicatedObjectId, o2oid[v]
    except KeyError:
        for new_oid in count(id(v)):
            if new_oid not in oid2o:
                break
        dedicated_object_set(new_oid, v)
        return DedicatedObjectNewId, new_oid


def dedicated_object_set(oid, o):
    if o is not oid2o.setdefault(oid, o):
        raise DedicatedObjectIdConflict(oid)


def dedicated_object_rename(cur_oid, new_oid):
    try:
        o = oid2o.pop(cur_oid)
    except KeyError:
        raise BadDedicatedObjectId(cur_oid)
    dedicated_object_set(new_oid, o)


def dedicated_object_translate(d):
    k, v = d
    if k is DedicatedAsIs:
        return v
    if k is DedicatedObjectId:
        return oid2o[v]
    if k is DedicatedIterable:
        return type(v)(map(dedicated_object_translate, v))
    if k is DedicatedDict:
        return dict(
            (n, dedicated_object_translate(vv)) for (n, vv) in v.items()
        )
    raise ValueError(k)


def dedicated_object_call(target, *a, **kw):
    return dedicated_object_translate_back(target(
        *map(dedicated_object_translate, a),
        **dict((n, dedicated_object_translate(v)) for (n, v) in kw.items()),
    ))


class DedicatedObjects(Dedicated):

    def __init__(self, *a, **kw):
        super(DedicatedObjects, self).__init__(*a, **kw)
        self.oid2op = {}
        self.o2op = {}

        # Object Proxy Front End
        opfe = self

        class ObjectProxy:

            def __getattr__(self, name):
                return opfe.getattr(id(self), name)

        self.ObjectProxy = ObjectProxy

    def getattr(self, oid, name):
        return self.translate_back(
            *self.call_asis(dedicated_object_getattr, oid, name)
        )

    def translate_back(self, kind, val):
        if kind is DedicatedAsIs:
            return val
        oid2op = self.oid2o
        if kind is DedicatedObjectId:
            return oid2op[val]
        assert kind is DedicatedObjectNewId
        ret = self.ObjectProxy()
        new_oid = id(ret)
        assert ret is oid2op.setdefault(new_oid, ret)
        self.call_asis(dedicated_object_rename, val, new_oid)
        return ret

    def account(self, o):
        try:
            ret = self.o2op[o]
        except KeyError:
            ret = self.ObjectProxy()
            self.o2op[o] = ret
        else:
            return ret
        new_oid = id(ret)
        assert ret is self.oid2op.setdefault(new_oid, ret)
        self.call_asis(dedicated_object_set, new_oid, o)
        return ret

    def translate(self, v):
        if dedicated_object_asis(v):
            return DedicatedAsIs, v
        if isinstance(v, self.ObjectProxy):
            return DedicatedObjectId, id(v)
        t = type(v)
        if t in (list, set, tuple):
            return DedicatedIterable, t(map(self.translate, v))
        if t is dict:
            translate = self.translate
            return DedicatedDict, dict(
                (n, translate(vv)) for (n, vv) in v.items()
            )
        return DedicatedObjectId, id(self.account(v))

    def launch(self, target, *a, **kw):
        translate = self.translate
        self.launch_asis(
            dedicated_object_call, target,
            *(map(translate, a)),
            **dict((n, translate(v)) for (n, v) in kw.items())
        )

    def poll(self, *a, **kw):
        return self.translate_back(*self.poll_asis(*a, **kw))

    def call_asis(self, target, *a, **kw):
        self.launch_asis(target, *a, **kw)
        return self.poll_asis()

    def launch_asis(self, *a, **kw):
        super(DedicatedObjects, self).launch(*a, **kw)

    def poll_asis(self, *a, **kw):
        return super(DedicatedObjects, self).poll(*a, **kw)
