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
    def __init__(self, name, parent = None):
        self.name = name

        # name : reference
        self.children = {}

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

    # Python serialization
    # This only means that the parent must be serialized first
    __pygen_deps__ = ("parent",)

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_args(self)
        gen.gen_end()

