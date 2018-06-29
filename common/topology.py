__all__ = [
    "GraphIsNotAcyclic"
  , "sort_topologically"
]

class GraphIsNotAcyclic(ValueError):
    pass


def dfs(node, visiting, visited):
    nid = id(node)

    if nid in visiting:
        raise GraphIsNotAcyclic()

    if nid in visited:
        return

    try:
        children = node.__dfs_children__
    except AttributeError:
        pass
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
