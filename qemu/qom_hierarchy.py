__all__ = [
    "QType"
]

from copy import (
    deepcopy as dcp
)
from common import (
    co_find_eq
)

class QType(object):
    """ Node in QOM type tree """
    def __init__(self, name, children = None, macro = None):
        self.name = name

        # name: reference
        self.children = children if children else {}
        for c in self.children.values():
            c.parent = self

        # list of macros corresponding to QType.name
        self.macro = macro if macro else []

        self.parent = None

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

    # Python serialization
    # Tree will be traversed from the root to the child nodes
    # And the children will be serialized first
    __pygen_deps__ = ("children",)

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_args(self)
        gen.gen_end()
