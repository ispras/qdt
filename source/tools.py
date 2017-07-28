__all__ = [
    "line_origins"
]

def line_origins(origins):
    """ Adds extra references to origins so the chunks of first one will be to
    the top of chunks of second one, and so on. """
    oiter = iter(origins)
    prev = next(oiter)

    for cur in oiter:
        try:
            refs = cur.extra_references
        except AttributeError:
            cur.extra_references = {prev}
        else:
            refs.add(prev)
        prev = cur
