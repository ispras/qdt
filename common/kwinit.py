__all__ = [
    "KWInit"
]


class KWInit:

    def __init__(self, *a, **kw):
        for kv in kw.items():
            setattr(self, *kv)
        self.__kwinit__(*a)

    def __kwinit__(self): pass
