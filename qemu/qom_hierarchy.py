__all__ = [
    "QType"
  , "from_legacy_dict"
]

from copy import (
    deepcopy as dcp
)
from common import (
    co_find_eq
)

class QType(object):
    """ Node in QOM type tree """
    def __init__(self, name, parent = None, children = None):
        self.name = name

        # name: reference
        self.children = children if children else {}
        for c in self.children.values():
            c.parent = self

        if parent is None:
            self.parent = None
        else:
            parent.__add_child(self)

    def __add_child(self, child):
        self.children[child.name] = child
        child.parent = self

    def __remove_child(self, child):
        child.parent = None
        del self.children[child.name]

    def unparent(self):
        self.parent.__remove_child(self)

    def root(self):
        """ returns root node, a one with `None` parent """
        root = self
        parent = root.parent
        while parent is not None:
            root = parent
            parent = root.parent
        return root

    def descendants(self):
        """ enumerates all nodes in depth-first order starting from self """
        root = self.root()
        stack = [root]

        while stack:
            e = stack.pop()
            yield e
            c = e.children
            if c:
                stack.extend(c.values())

    def find(self, **request):
        """ searches for the request across entire tree starting from root """
        for t in co_find_eq(self.root().descendants(), **request):
            yield t

    # Tree will be traversed from the root to the child nodes
    # The children will be serialized first
    __pygen_deps__ = ("children",)

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_args(self, skip_list = ["parent"])
        gen.gen_end()

def from_dict(d, parent = None):
    res = QType(d["type"], parent = parent)
    for key, val in d.items():
        if key == "children":
            continue
        if key == "type":
            continue
        setattr(res, key, dcp(val))
    return res

def from_legacy_dict(dt):
    stack = [(None, dt[0])]
    while stack:
        parent, tdict = stack.pop()
        t = from_dict(tdict, parent = parent)

        try:
            children = tdict["children"]
        except KeyError:
            continue

        stack.extend((t, child_dict) for child_dict in children)

    # note that any intermediate value is proper
    return t.root()

