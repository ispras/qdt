__all__ = [
    "GraphIsNotAcyclic"
  , "sort_topologically"
  , "flatten"
]


def flatten(i):
    "Recursively flattens iterable in depth first order"
    # Refs:
    # https://stackoverflow.com/questions/1952464/in-python-how-do-i-determine-if-an-object-is-iterable
    # https://codereview.stackexchange.com/questions/49877/recursive-flatten-with-lazy-evaluation-iterator
    try:
        # if `i` is an iterable then iterate its `item`s and flatten them
        # recursively.
        for item in i:
            for subitem in flatten(item):
                yield subitem
    except TypeError:
        # Else, just yield `i`
        yield i


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
