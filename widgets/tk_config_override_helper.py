__all__ = [
    "TkConfigureOverrideHelper"
]

from six.moves.tkinter import (
    _cnfmerge,
)


class TkConfigureOverrideHelper(
    object  # extra options are to be `@property`-like
):
    """ Maps `__extra_cnfigure_options__` of `configure` family calls to
`getattr`/`setattr` interface. Intended to be used with `@property`.
    """

    __extra_cnfigure_options__ = ()

    def configure(self, cnf = None, **kw):
        if kw:
            cnf = _cnfmerge((cnf, kw))
        elif cnf:
            cnf = _cnfmerge(cnf)
        eco = self.__extra_cnfigure_options__
        if cnf is None:
            return _cnfmerge((
                super(type(self), self).configure(),
                dict((o, getattr(self, o)) for o in eco)
            ))
        if isinstance(cnf, str):
            if cnf in eco:
                return getattr(self, cnf)
            return super(type(self), self).configure(cnf)
        for o in tuple(cnf):
            if o in eco:
                setattr(self, o, cnf.pop(o))
        if cnf:
            return super(type(self), self).configure(cnf)

    config = configure

    def cget(self, key):
        if key in self.__extra_cnfigure_options__:
            return getattr(self, key)
        return super(type(self), self).cget(key)
