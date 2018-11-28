__all__ = [
    "GraphIsNotAcyclic"
  , "sort_topologically"
]

from .visitor import (
    ObjectVisitor,
    BreakVisiting
)
from collections import (
    deque
)
from six import (
    moves
)

builtin_types = [
    t for t in moves.builtins.__dict__.values() if isinstance(t, type)
] + [type(None)]


class GraphIsNotAcyclic(ValueError):
    pass


class TopologyVisitor(ObjectVisitor):
    def __init__(self, root, field_name = "__dfs_attrs__"):
        self.objects = deque()
        super(TopologyVisitor, self).__init__(root, field_name)

    def on_visit(self):
        if type(self.cur) not in builtin_types:
            self.objects.append(self.cur)
            raise BreakVisiting()


def dfs(node, visiting, visited):
    nid = id(node)

    if nid in visiting:
        raise GraphIsNotAcyclic()

    if nid in visited:
        return

    try:
        get_children = node.__dfs_children__
    except AttributeError:
        tv = TopologyVisitor(node, field_name = "__dfs_attrs__")

        tv.visit()

        children = list(reversed(tv.objects))
    else:
        children = get_children()

    visiting.add(nid)

    for n in children:
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
