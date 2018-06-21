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


def sort_topologically(roots = []):
    """
    Objects in the trees do implement __dfs_children__ method. This method
    returns an iterable of objects to each of whose an edge exists.
    Leafs may either return empty iterable or do not implement
    __dfs_children__ at all.
    """

    ret = []
    visiting = set()
    visited = set()

    # reverse sequence returned
    for node in roots:
        for n in dfs(node, visiting, visited):
            ret.append(n)

    return ret
