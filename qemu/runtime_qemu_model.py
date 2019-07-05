__all__ = [
    "RQOMTree"
  , "RQOMType"
  , "RQObjectProperty"
  , "RQInstance"
]

from .qom_common import (
    QOMPropertyTypeLink,
    QOMPropertyTypeString,
    QOMPropertyTypeBoolean,
    QOMPropertyTypeInteger,
    QOMPropertyValue
)
from common import (
    lazy
)
from debug import (
    TYPE_CODE_PTR
)
from collections import (
    defaultdict
)

class RQOMTree(object):
    "QEmu object model tree descriptor at runtime"

    def __init__(self):
        self.name2type = {}
        self.addr2type = {}

        # Types are found randomly (i.e. not in parent-first order).
        self.unknown_parents = defaultdict(list)

    def account(self, impl, name = None, parent = None):
        """ Add a type.
    :type impl: debug.Value
    :param impl:
        is the value of type's `TypeImpl` struct
        """

        if impl.type.code == TYPE_CODE_PTR:
            # Pointer `impl` is definitely a value on the stack. It cannot be
            # used as a global. Same time `TypeImpl` is on the heap. Hence, it
            # can. I.e. a dereferenced `Value` should be used.
            impl = impl.dereference()
        if not impl.is_global:
            impl = impl.to_global()

        info_addr = impl.address

        t = RQOMType(self, impl, name = name, parent = parent)

        name = t.name
        parent = t.parent

        self.addr2type[info_addr] = t
        self.name2type[name] = t

        unk_p = self.unknown_parents

        n2t = self.name2type
        if parent in n2t:
            n2t[parent].children.append(t)
        else:
            unk_p[parent].append(t)

        if name in unk_p:
            t.children.extend(unk_p.pop(name))

        return t

    def __getitem__(self, addr_or_name):
        if isinstance(addr_or_name, str):
            return self.name2type[addr_or_name]
        else:
            return self.addr2type[addr_or_name]


class RQOMType(object):
    "QEmu object model type descriptor at runtime"

    def __init__(self, tree, impl, name = None, parent = None):
        """
    :type impl: debug.Value
    :param impl:
        is a global variable of type `TypeImpl`

    :type name: str
    :param name:
        is given if it is already known else it will be got from `impl`

    :type parent: str
    :param parent:
        is given if it is already known else it will be got from `impl`

        """
        self.tree = tree
        self.impl = impl
        if name is None:
            name = impl["name"].fetch_c_string()
        if parent is None:
            parent = impl["parent"].fetch_c_string()
            # Parent may be None
        self.name, self.parent = name, parent

        self.properties = []

        self.children = []

        # Instance pointer can be casted to different C types. Remember those
        # types.
        self.instance_casts = set()

        # "device"
        self.realize = None

    def instance_casts(self):
        """ A QOM instance can also be casted to C types those corresponds to
ancestors.
    :returns: list of possible casts (debug.Type)
        """
        ret = set(self.instance_casts)
        for a in self.iter_ancestors():
            for cast in a.instance_casts:
                ret.add(cast)
        return ret

    # TODO: there is too many boilerplate code for `TypeImpl` fields access.
    # Consider to rewrite it in a common way. `__getitem__` ?

    @lazy
    def instance_init(self):
        impl = self.impl

        addr = impl["instance_init"].fetch_pointer()
        if addr:
            return impl.dic.subprogram(addr)
        return None

    @lazy
    def class_init(self):
        impl = self.impl

        addr = impl["class_init"].fetch_pointer()
        if addr:
            return impl.dic.subprogram(addr)
        return None

    def __dfs_children__(self):
        return self.children

    def iter_ancestors(self):
        n2t = self.tree.name2type
        cur = self.parent

        while cur is not None:
            t = n2t[cur]
            yield t
            cur = t.parent

    def iter_inheritance(self):
        yield self

        for a in self.iter_ancestors():
            yield a

    def implements(self, name):
        if name == self.name:
            return True

        try:
            t = self.tree.name2type[name]
        except KeyError:
            # the type given is unknown, `self` cannot implement it
            return False

        for a in self.iter_ancestors():
            if a is t:
                return True
        return False


class RQObjectProperty(object):
    "Represents runtime state of QOM object property"

    def __init__(self, owner, prop, name = None, _type = None):
        """
    :type owner: RQInstance or RQOMType
    :param owner:
        is owner of that property
    :type prop: debug.Value
    :param prop:
        represents corresponding variable of type `ObjectProperty`
        """
        self.owner = owner
        self.prop = prop
        if name is None:
            name = prop["name"].fetch_c_string()
        if _type is None:
            _type = prop["type"].fetch_c_string()
        self.name = name
        self.type = _type

    @lazy
    def as_qom(self):
        "Converts to property model from `qemu` module."
        # XXX: note that returned values are not default
        t = self.type
        if t.startswith("int") or t.startswith("uint"):
            return QOMPropertyValue(QOMPropertyTypeInteger, self.name, 0)
        elif t.startswith("link<"):
            return QOMPropertyValue(QOMPropertyTypeLink, self.name, None)
        elif t == "bool":
            return QOMPropertyValue(QOMPropertyTypeBoolean, self.name, False)
        else:
            return QOMPropertyValue(QOMPropertyTypeString, self.name, "")


class RQInstance(object):
    "Descriptor for QOM object at runtime."

    def __init__(self, obj, _type):
        """
    :type obj: debug.Value
    :param obj:
        is runtime variable representing that instance

    :type type: RQOMType
    :param type:
        is descriptor for QOM type of that instance
        """
        self.obj = obj
        self.type = _type
        self.related = []


        # QOM type specific fields

        # object
        self.properties = {}

        # qemu:memory-region:
        # bus
        self.name = None

        # qemu:memory-region
        self.size = None

        # device: the bus this device is attached to
        # bus: the device controlling this bus
        self.parent = None

        # device: buses controlled by the device
        # bus: devices on the bus
        self.children = []

        # irq:
        # tuple (dev. `RQInstance`, GPIO name, GPIO index)
        #     for split IRQ: `dst[0]` is `self`
        self.src = None
        self.dst = None

    def relate(self, qinst):
        self.related.append(qinst)
        qinst.related.append(self)

    def unrelate(self, qinst):
        self.related.remove(qinst)
        qinst.related.renove(self)

    def account_property(self, prop):
        """ Helper for property accounting.

    :type prop: Value
    :param prop:
        represents corresponding variable of type `ObjectProperty`
        """
        if prop.type.code == TYPE_CODE_PTR:
            prop = prop.dereference()
        if not prop.is_global:
            prop = prop.to_global()

        rqo_prop = RQObjectProperty(self, prop)
        self.properties[rqo_prop.name] = rqo_prop

        return rqo_prop
