__all__ = [
    "lazy"
]


class lazy(object):

    def __init__(self, getter):
        self.getter = getter

    def __get__(self, obj, cls):
        getter = self.getter
        val = getter(obj)
        """ Replace itself with the computed value to prevent consequent getter
        calls.
        see: https://stackoverflow.com/questions/23552536/override-property-getter-in-runtime
        """
        setattr(obj, getter.__name__, val)
        return val
