__all__ = [
    "iter_snake_case"
  , "snake_case"
]


def snake_case(idname):
    return "".join(iter_snake_case(idname))


def iter_snake_case(idname):
    niter = iter(idname)
    # Don't prefix first title character with `_`.
    try:
        yield next(niter).lower()
    except StopIteration:
        return
    for c in niter:
        if c.istitle():
            yield "_" + c.lower()
        else:
            yield c
