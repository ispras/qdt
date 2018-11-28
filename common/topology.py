__all__ = [
    "GraphIsNotAcyclic"
  , "sort_topologically"
]

from .visitor import (
    ObjectVisitor
)
from collections import (
    deque
)
# this code based on
# https://stackoverflow.com/questions/3210238/how-do-i-get-list-of-all-python-
# types-programmatically
try :
    # python2
    import __builtin__

    builtin_types = [
        t for t in __builtin__.__dict__.itervalues() if isinstance(t, type)
    ]
except ImportError:
    # python3
    import builtins

    builtin_types = [
        getattr(builtins, d) for d in dir(builtins)
        if isinstance(getattr(builtins, d), type)
    ]

builtin_types.append(type(None))

class GraphIsNotAcyclic(ValueError):
    pass


class TopologyVisitor(ObjectVisitor):
    def __init__(self, root):
        self.objects = deque()
        super(TopologyVisitor, self).__init__(root)

    def on_visit(self):
        if type(self.cur) not in builtin_types:
            self.objects.append(self.cur)


def dfs(node, visiting, visited):
    nid = id(node)

    if nid in visiting:
        raise GraphIsNotAcyclic()

    if nid in visited:
        return

    try:
        children = node.__dfs_children__
    except AttributeError:
        tv = TopologyVisitor(node)

        tv.visit()

        for n in list(reversed(tv.objects)):
            yield n
    else:
        visiting.add(nid)

        for n in children():
            for nn in dfs(n, visiting, visited):
                yield nn

        visiting.remove(nid)

    visited.add(nid)

    yield node


def sort_topologically(roots):
    """ Given roots of object trees this generator iterates objects in depth
first topology order. A tree is defined by `__dfs_children__` method of each
its node. One must return an iterable of its node children. A leaf node may
either return an empty iterable or do not implement `__dfs_children__` at all.
    """

    visiting = set()
    visited = set()

    for node in roots:
        for n in dfs(node, visiting, visited):
            yield n
