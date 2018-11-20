__all__ = [
    "trie_add"
  , "trie_find"
]

# Helpers to build trie of `dict`s


def trie_add(trie, path, value, replace = False):
    """
    :trie: is a starting node
    :path: is a list (or any indexable & slicable) of hashables
    :value: to add
    :returns: either added value or the value that already is in the trie
    """

    while path:
        part = path[0]
        path = path[1:]
        if part in trie:
            other = trie[part]

            if isinstance(other, tuple):
                # Only one value with such prefix is in the trie for now.
                # Convert leaf node to a branch to store the value being
                # added.
                other_value, other_path = other

                if other_path == path:
                    # this path is already in the trie
                    if replace:
                        trie[part] = (value, path)

                    return other_value

                if other_path:
                    other_p = other_path[0]
                    other_path = other_path[1:]

                    other = {
                        other_p : (other_value, other_path)
                    }
                else:
                    other = {
                        None : other_value
                    }

                trie[part] = other

            trie = other
        else:
            # Completely new path in the trie. Do not convert rest path to
            # subtries without a need.
            trie[part] = (value, path)
            return value

    # There are several paths with such _prefix_. Is there an exact such
    # _path_?

    if None in trie:
        return trie[None]
    else:
        trie[None] = value
        return value


def trie_find(trie, path):
    """
    :trie: is a starting node
    :path: is a list (or any indexable & slicable) of hashables
    :returns: the value that already is in the trie
    :raises:
        KeyError if there is no a value with such path
        ValueError if there are several values with such path prefix
    """

    for i, p in enumerate(path, 1):
        if p not in trie:
            break

        v = trie[p]

        if isinstance(v, dict):
            # There are several nodes with such path prefix. Try next suffix
            # part.
            trie = v
            continue

        # There is only one value with such path prefix in the tree.
        value, rest = v

        # Check parts of current value path those are not in the tree yet.
        if rest[:len(path) - i] == path[i:]:
            return value
        else:
            # Some parts differs.
            break
    else:
        # Provided path is fully traversed. Is there a value with exactly
        # such path?
        if None in trie:
            return trie[None]

        raise ValueError("Given path %s is not long enough to look value"
            " up unambiguously. There are several values with such path"
            " prefix." % str(path)
        )

    raise KeyError("No path %s" % str(path))
