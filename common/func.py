__all__ = [
    "bind"
]

def bind(func, *a, **kw):
    "Binds values to arguments of the `func`tion."
    return lambda *_a, **_kw : func(*(a + _a), **(kw.update(_kw) or kw))
