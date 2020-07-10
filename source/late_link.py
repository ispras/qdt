__all__ = [
    "LateLink"
]


class LateLink(object):
    """ A placeholder for a entity that does not exist yet (or reference is
inaccessible). It will be replaced with a reference to the entity.
    """

    def __init__(self, key):
        """
:param key:
    A key to search the entity.
    Type and interpretation depend on lookup scope.

    `BodyTree` scope (of a `Function`):
      - local `Variable`

    `Function` scope:
      - `int`eger index of an argument
      - `str`ing name of an argument.

    `Source` scope:
      - `str`ing name of a global `Variable`
      - `str`ing name of a `Type`

    * Lookup order from inner scope to outer (top-down in the list).

        """
        self.key = key

    def gen_defining_chunk_list(self, *__, **__):
        raise RuntimeError("Late link '%s' is not resolved" % self.key)
