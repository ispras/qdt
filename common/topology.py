__all__ = [
    "GraphIsNotAcyclic",
    "sort_topologically"
]

# All objects (nodes) should NOT use __dfs_visited__ name in its namespace.
# All objects in tree should implement __dfs_children__ method.
# The method should return list of objects, to which an edge exists, or [], if
# the object is leaf.

# __dfs_visited__: 
# AttributeError - not visited
# 1 - under processing
# 2 - processed

class GraphIsNotAcyclic(Exception):
    pass

def dfs(node):
    try:
        if node.__dfs_visited__ == 1:
            raise GraphIsNotAcyclic
        # This is not actually needed
        #elif node.__dfs_visited__ == 2:
        #    raise StopIteration
    except AttributeError:
        node.__dfs_visited__ = 1
        for n in node.__children__():
            for nn in dfs(n):
                yield nn
        node.__dfs_visited__ = 2
        yield node

    raise StopIteration

def sort_topologically(roots = []):
    ret = []
    # reverse sequence returned
    for node in roots:
        for n in dfs(node):
            ret.append(n)
    for node in ret:
        del node.__dfs_visited__
    return ret
