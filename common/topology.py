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

    visiting.add(nid)

    for n in node.__dfs_children__():
        for nn in dfs(n, visiting, visited):
            yield nn

    visiting.remove(nid)
    visited.add(nid)

    yield node


def sort_topologically(roots = []):
    """
    All objects in the trees should implement __dfs_children__ method. This
    method should return list of objects, to which an edge exists, or [], if
    the object is a leaf.
    """

    ret = []
    visiting = set()
    visited = set()

    # reverse sequence returned
    for node in roots:
        for n in dfs(node, visiting, visited):
            ret.append(n)

    return ret
